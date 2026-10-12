"""Pure count-domain activity extraction; caller assertions never grant run authority."""

from fractions import Fraction
import math
import statistics

QUARTER = 250_000_000
SECOND = 1_000_000_000
HORIZONS = (1, 3, 5)
MAX_PIECES = 32_768
MAX_SAMPLES = 8_000_000
MAX_ABS_VALUE = 1e12
STATUSES = ("available", "DEFERRED_DEV", "UNSUPPORTED", "LATE_BASE", "GROUP_INELIGIBLE",
            "BAD_NOISE_COVERAGE", "BAD_NOISE_NUMBER", "BAD_WINDOW_COVERAGE", "BAD_WINDOW_NUMBER")


class InvalidInput(ValueError):
    """A bounded schema failure without embedding caller values."""


def _keys(obj, expected):
    if type(obj) is not dict or any(type(key) is not str for key in obj):
        raise InvalidInput("SCHEMA")
    if set(obj) != set(expected):
        raise InvalidInput("SCHEMA")


def _integer(x, lo, hi):
    if type(x) is not int or not lo <= x <= hi:
        raise InvalidInput("INTEGER")
    return x


def _number(x, limit=MAX_ABS_VALUE):
    if type(x) not in (int, float) or abs(x) > limit:
        raise InvalidInput("NUMBER")
    y = float(x)
    if not math.isfinite(y):
        raise InvalidInput("NUMBER")
    return y


def _text(x, allowed=None):
    if type(x) is not str or not 1 <= len(x) <= 128:
        raise InvalidInput("TEXT")
    if allowed is not None and x not in allowed:
        raise InvalidInput("ENUM")
    return x


def _unknown(seconds, reason):
    return {
        "seconds": seconds, "status": reason, "ratios": [], "states": [],
        "run_ages": [], "transitions": [], "episodes": [],
        "noise_power": [], "noise_floor": [],
    }


def _piece_geometry(components, family):
    if type(components) is not list or len(components) != 3:
        raise InvalidInput("COMPONENTS")
    expected = set("ENZ" if family == "ENZ" else "12Z")
    suffixes, prefixes, prepared, ordered_suffixes = set(), set(), [], []
    total_pieces = total_samples = 0
    for component in components:
        _keys(component, ("name", "pieces"))
        name = component["name"]
        if type(name) is not str or len(name) != 3 or not name.isascii():
            raise InvalidInput("CHANNEL")
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in name):
            raise InvalidInput("CHANNEL")
        suffixes.add(name[-1])
        ordered_suffixes.append(name[-1])
        prefixes.add(name[:2])
        pieces = component["pieces"]
        if type(pieces) is not list or not 1 <= len(pieces) <= MAX_PIECES:
            raise InvalidInput("PIECES")
        total_pieces += len(pieces)
        parsed, previous_start = [], None
        for piece in pieces:
            _keys(piece, ("start_ns", "rational_period", "values"))
            start = _integer(piece["start_ns"], -(2**63), 2**63 - 1)
            period = piece["rational_period"]
            if type(period) is not list or len(period) != 2:
                raise InvalidInput("PERIOD")
            num = _integer(period[0], 1, 10**12)
            den = _integer(period[1], 1, 10**9)
            if math.gcd(num, den) != 1:
                raise InvalidInput("PERIOD_CANONICAL")
            values = piece["values"]
            if type(values) not in (list, tuple) or not 1 <= len(values) <= MAX_SAMPLES:
                raise InvalidInput("VALUES_CONTAINER")
            total_samples += len(values)
            if previous_start is not None and start <= previous_start:
                raise InvalidInput("PIECE_ORDER")
            previous_start = start
            step = Fraction(num, den)
            parsed.append((Fraction(start), step, start + len(values) * step, values))
        prepared.append(parsed)
    if total_pieces > MAX_PIECES or total_samples > MAX_SAMPLES:
        raise InvalidInput("EVENT_CAP")
    if (suffixes != expected or len(prefixes) != 1
            or ordered_suffixes != list("ENZ" if family == "ENZ" else "12Z")):
        raise InvalidInput("LITERAL_FAMILY")
    return prepared


def _ceil(x):
    return -((-x.numerator) // x.denominator)


def _window_values(pieces, lo, hi):
    """No repair/merge: independently visit exact half-open record views."""
    cursor, count = Fraction(lo), 0
    for start, step, end, values in pieces:
        if end <= lo or start >= hi:
            continue
        left, right = max(start, lo), min(end, hi)
        if left != cursor:
            raise InvalidInput("COVERAGE")
        cursor = right
        first = max(0, _ceil((Fraction(lo) - start) / step))
        last = min(len(values), _ceil((Fraction(hi) - start) / step))
        for index in range(first, last):
            # Only currently cropped values are inspected, including numeric validation.
            count += 1
            yield _number(values[index])
    if cursor != hi or count == 0:
        raise InvalidInput("COVERAGE")


def _mean(pieces, lo, hi, center=0.0, squared=False):
    count = 0

    def terms():
        nonlocal count
        for value in _window_values(pieces, lo, hi):
            count += 1
            value -= center
            yield value * value if squared else value

    total = math.fsum(terms())
    return total / count


def _noise(prepared, t0):
    centers, powers, floors = [], [], []
    for pieces in prepared:
        center = _mean(pieces, t0 - 3 * SECOND, t0)
        cells = [
            _mean(pieces, t0 - 3 * SECOND + j * QUARTER,
                  t0 - 3 * SECOND + (j + 1) * QUARTER, center, True)
            for j in range(12)
        ]
        raw = statistics.median(cells)
        centers.append(center)
        powers.append(max(1.0, raw))
        floors.append(raw < 1.0)
    return centers, powers, floors


def _sequence(ratios):
    states = [int(ratio > 9.0) for ratio in ratios]
    ages, transitions, episodes = [], [], []
    age, episode_start = 0, 1
    for index, state in enumerate(states):
        if index and state != states[index - 1]:
            transitions.append({"cell": index + 1,
                                "kind": "off" if state == 0 else "on",
                                "prior_run_age": age})
            episodes.append({"state": states[index - 1], "start_cell": episode_start,
                             "cells": age, "right_censored": False})
            episode_start, age = index + 1, 0
        age += 1
        ages.append(age)
    if states:
        episodes.append({"state": states[-1], "start_cell": episode_start,
                         "cells": age, "right_censored": True})
    return states, ages, transitions, episodes


def extract_event(event, qualification):
    """Return private bounded scalars; DEV/denied TRAIN values must be absent.

    Qualification is root-supplied support assertion, NOT evidence of custody,
    runtime, grouping, transport, decoding or authority to perform actual IO.
    """
    _keys(event, ("slot", "partition", "t0_ns", "p_ns", "family", "mw",
                  "group", "components"))
    _keys(qualification, ("horizon_support", "group_eligible"))
    support = qualification["horizon_support"]
    if type(support) is not list or len(support) != 3 or any(type(v) is not bool for v in support):
        raise InvalidInput("SUPPORT")
    if type(qualification["group_eligible"]) is not bool:
        raise InvalidInput("GROUP_ELIGIBILITY")
    slot = _integer(event["slot"], 0, 114)
    partition = _text(event["partition"], ("TRAIN", "DEV"))
    t0 = _integer(event["t0_ns"], -(2**63) + 3 * SECOND, 2**63 - 1 - 5 * SECOND)
    p = _integer(event["p_ns"], t0, 2**63 - 1)
    mw = _number(event["mw"])
    if not -5.0 <= mw <= 15.0:
        raise InvalidInput("MW")
    group = event["group"]
    if group is not None:
        _text(group)
    family = event["family"]
    if family is not None:
        _text(family, ("ENZ", "12Z"))
    result = {"schema": "activity-event-v1", "slot": slot, "partition": partition,
              "family": family, "mw": mw, "group": group,
              "external_support_asserted": list(support), "all_horizon_eligible": False,
              "external_group_eligible_asserted": qualification["group_eligible"],
              "horizons": []}
    denied = ("DEFERRED_DEV" if partition == "DEV" else
              "UNSUPPORTED" if family is None or not all(support) else
              "LATE_BASE" if p + QUARTER > t0 + SECOND else
              "GROUP_INELIGIBLE" if group is None or not qualification["group_eligible"] else None)
    if denied:
        if event["components"] is not None:
            raise InvalidInput("DENIED_VALUES_MUST_BE_ABSENT")
        result["horizons"] = [_unknown(h, denied) for h in HORIZONS]
        return result
    prepared = _piece_geometry(event["components"], family)
    try:
        centers, powers, floors = _noise(prepared, t0)
    except InvalidInput as error:
        result["horizons"] = [_unknown(h, "BAD_NOISE_" + str(error)) for h in HORIZONS]
        return result
    for horizon in HORIZONS:
        try:
            number = (t0 + horizon * SECOND - p) // QUARTER
            ratios = []
            for j in range(number):
                lo, hi = p + j * QUARTER, p + (j + 1) * QUARTER
                ratios.append(max(_mean(pieces, lo, hi, center, True) / power
                                  for pieces, center, power in zip(prepared, centers, powers)))
            states, ages, transitions, episodes = _sequence(ratios)
            result["horizons"].append({"seconds": horizon, "status": "available",
                                       "ratios": ratios, "states": states, "run_ages": ages,
                                       "transitions": transitions, "episodes": episodes,
                                       "noise_power": list(powers), "noise_floor": list(floors)})
        except InvalidInput as error:
            result["horizons"].append(_unknown(horizon, "BAD_WINDOW_" + str(error)))
    result["all_horizon_eligible"] = all(h["status"] == "available" for h in result["horizons"])
    return result


def summarize(results, external):
    """TRAIN-only operational-group variation; never certifies physical independence."""
    _keys(external, ("grouping_frozen", "prior_support_floor_pass"))
    if any(type(value) is not bool for value in external.values()):
        raise InvalidInput("EXTERNAL")
    if type(results) is not list or len(results) != 115:
        raise InvalidInput("COHORT_SIZE")
    counts = {"TRAIN": 0, "DEV": 0}
    usable, off_groups, censored_groups, terminal_ages = [], set(), set(), set()
    statuses, family_counts, floor_counts = {}, {}, {"ENZ": [0, 0, 0], "12Z": [0, 0, 0]}
    for slot, result in enumerate(results):
        _keys(result, ("schema", "slot", "partition", "family", "mw", "group",
                       "external_support_asserted", "external_group_eligible_asserted",
                       "all_horizon_eligible", "horizons"))
        if type(result["schema"]) is not str or result["schema"] != "activity-event-v1":
            raise InvalidInput("RESULT_SCHEMA")
        if _integer(result["slot"], 0, 114) != slot:
            raise InvalidInput("COHORT_ORDER")
        partition = _text(result["partition"], ("TRAIN", "DEV"))
        counts[partition] += 1
        if type(result["all_horizon_eligible"]) is not bool:
            raise InvalidInput("ELIGIBILITY")
        if type(result["external_group_eligible_asserted"]) is not bool:
            raise InvalidInput("GROUP_ELIGIBILITY")
        support = result["external_support_asserted"]
        if type(support) is not list or len(support) != 3 or any(type(v) is not bool for v in support):
            raise InvalidInput("SUPPORT")
        group = result["group"]
        if group is not None:
            _text(group)
        mw = _number(result["mw"])
        if not -5 <= mw <= 15:
            raise InvalidInput("MW")
        family = result["family"]
        if family is not None:
            _text(family, ("ENZ", "12Z"))
        horizons = result["horizons"]
        if type(horizons) is not list or len(horizons) != 3:
            raise InvalidInput("HORIZONS")
        for seconds, cell in zip(HORIZONS, horizons):
            _keys(cell, ("seconds", "status", "ratios", "states", "run_ages",
                         "transitions", "episodes", "noise_power", "noise_floor"))
            if _integer(cell["seconds"], 1, 5) != seconds:
                raise InvalidInput("HORIZON_ORDER")
            status = _text(cell["status"], STATUSES)
            key = partition + ":" + str(seconds) + ":" + status
            statuses[key] = statuses.get(key, 0) + 1
            for name in ("ratios", "states", "run_ages", "transitions", "episodes"):
                if type(cell[name]) is not list or len(cell[name]) > 20:
                    raise InvalidInput("CELL_CAP")
            for name in ("noise_power", "noise_floor"):
                if type(cell[name]) is not list or len(cell[name]) > 3:
                    raise InvalidInput("NOISE_CAP")
            if status == "available":
                if (partition == "DEV" or not all(support) or family is None
                        or group is None or not result["external_group_eligible_asserted"]):
                    raise InvalidInput("UNSUPPORTED_RESULT")
                ratios = [_number(x, 1e25) for x in cell["ratios"]]
                if not ratios or any(x < 0 for x in ratios):
                    raise InvalidInput("RATIOS")
                # Eligible P delay is0..0.75s; cumulative quarter counts grow by8.
                if not 4 * seconds - 3 <= len(ratios) <= 4 * seconds:
                    raise InvalidInput("HORIZON_LENGTH")
                expected = _sequence(ratios)
                # Exact built-in structures prevent hostile equality in caller output.
                _validate_sequence_fields(cell)
                if (cell["states"], cell["run_ages"], cell["transitions"], cell["episodes"]) != expected:
                    raise InvalidInput("SEQUENCE")
                if type(cell["noise_floor"]) is not list or len(cell["noise_floor"]) != 3 or any(type(x) is not bool for x in cell["noise_floor"]):
                    raise InvalidInput("FLOORS")
                if type(cell["noise_power"]) is not list or len(cell["noise_power"]) != 3 or any(_number(x, 1e25) < 1 for x in cell["noise_power"]):
                    raise InvalidInput("NOISE")
            elif any(cell[name] for name in ("ratios", "states", "run_ages", "transitions", "episodes", "noise_power", "noise_floor")):
                raise InvalidInput("UNKNOWN_SCALARS")
        available = [cell for cell in horizons if cell["status"] == "available"]
        for earlier, later in zip(available, available[1:]):
            difference = 4 * (later["seconds"] - earlier["seconds"])
            if (len(later["ratios"]) != len(earlier["ratios"]) + difference
                    or later["ratios"][:len(earlier["ratios"])] != earlier["ratios"]
                    or later["noise_power"] != earlier["noise_power"]
                    or later["noise_floor"] != earlier["noise_floor"]):
                raise InvalidInput("HORIZON_PREFIX")
        actual = all(cell["status"] == "available" for cell in horizons)
        if actual != result["all_horizon_eligible"]:
            raise InvalidInput("ELIGIBILITY")
        if partition == "TRAIN" and actual:
            usable.append(mw)
            last = horizons[-1]
            family_counts[family] = family_counts.get(family, 0) + 1
            floor_counts[family] = [a + int(b) for a, b in zip(floor_counts[family], last["noise_floor"])]
            off = [t for t in last["transitions"] if t["kind"] == "off"]
            if off:
                off_groups.add(group)
                terminal_ages.update(t["prior_run_age"] for t in off)
            episode = last["episodes"][-1]
            if episode["state"] == 1 and episode["right_censored"]:
                censored_groups.add(group)
                terminal_ages.add(episode["cells"])
    if counts != {"TRAIN": 91, "DEV": 24}:
        raise InvalidInput("PARTITION_COUNTS")
    observed = (len(off_groups) >= 5 and len(censored_groups) >= 5 and len(terminal_ages) >= 2
                and any(mw >= 5.5 for mw in usable) and any(mw < 5.5 for mw in usable))
    return {"schema": "activity-summary115-v1", "events": 115, "horizon_cells": 345,
            "partition_counts": counts, "status_counts": statuses,
            "usable_train_events": len(usable), "train_family_counts": family_counts,
            "train_noise_floor_counts_by_family_literal_order": floor_counts,
            "off_train_operational_groups": len(off_groups),
            "active_censored_train_operational_groups": len(censored_groups),
            "distinct_terminal_active_run_ages": sorted(terminal_ages),
            "observational_variation_pass": observed,
            "external_grouping_frozen_asserted": external["grouping_frozen"],
            "external_prior_support_floor_asserted": external["prior_support_floor_pass"],
            "combined_prospective_gate": observed and all(external.values()),
            "fit_authorized": False, "physical_rupture_state_verified": False,
            "population_bulk_preservation_verified": False}


def _validate_sequence_fields(cell):
    for state in cell["states"]:
        _integer(state, 0, 1)
    for age in cell["run_ages"]:
        _integer(age, 1, 20)
    for transition in cell["transitions"]:
        _keys(transition, ("cell", "kind", "prior_run_age"))
        _integer(transition["cell"], 2, 20)
        _text(transition["kind"], ("on", "off"))
        _integer(transition["prior_run_age"], 1, 20)
    for episode in cell["episodes"]:
        _keys(episode, ("state", "start_cell", "cells", "right_censored"))
        _integer(episode["state"], 0, 1)
        _integer(episode["start_cell"], 1, 20)
        _integer(episode["cells"], 1, 20)
        if type(episode["right_censored"]) is not bool:
            raise InvalidInput("CENSORED")
