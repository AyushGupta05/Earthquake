"""L-only bridge: pinned prior/proper formulas and explicit observed-level law."""
import math
import time
import numpy as np
import torch
from torch import nn

LAW = 'shared-level-reference-AR-L-v1'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


class SharedBudget:
    def __init__(self, begin):
        need(type(begin) in (int, float) and math.isfinite(begin) and 0 <= begin <= time.monotonic(), 'processing_begin')
        self.begin = begin
        self.points = 0
        self.terms = 0
        self.tick()

    def charge(self, points, terms):
        need(type(points) is int and type(terms) is int and points >= 0 and terms >= 0, 'work')
        need(self.points + points <= 1000000, 'evaluation_cap')
        self.points += points
        self.terms += terms
        self.tick()

    def check(self, points=0, terms=0):
        self.charge(points, terms)

    def tick(self):
        need(time.monotonic() - self.begin <= 10, 'deadline')

    def record(self):
        return dict(density_points=self.points, scalar_terms=self.terms, seconds=time.monotonic()-self.begin)


class LNet(nn.Module):
    def __init__(self, operator, k, mref):
        super().__init__()
        need(type(mref) in (int, float) and math.isfinite(mref) and abs(mref) <= 1e6, 'mref')
        self.prior = operator.Prior(k)
        self.arm = 'L'
        self.mref = float(mref)
        # Traversal and exact initial18 values match the original MarkedNet.
        self.coefficients = nn.Parameter(torch.tensor([[0., .1, 0., .01, .1, math.log(math.expm1(.95))]]*3, dtype=torch.float64))


def forecast(operator, kernel, prior, marks, coeff, nu, mref, horizon, offset, target, *, processing_begin):
    budget = SharedBudget(processing_begin)
    target_tensor = torch.tensor([target], dtype=torch.float64)
    result = kernel.marked_nll(tuple(x[None, :] for x in prior), (marks,), coeff, nu[None, :, :],
                               target_tensor, 'L', mref, (horizon,), (offset,), processing_begin=processing_begin)
    budget.charge(result['density_points'][0], result['density_points'][0])
    facts = []
    for j, (a, b, s, y) in enumerate(operator.affine(coeff, marks, mref)):
        previous = marks[j-1] if j else marks.new_zeros(3)
        facts.append(dict(cell=j, intercept=a.detach().clone(), slope=b.detach().clone(), sigma=s.detach().clone(),
                          value=y.detach().clone(), previous=previous.detach().clone(), loading=result['loadings'][j].detach().clone()))
    ref = dict(arm='L', prior=[v.detach().clone() for v in prior], coefficients=coeff.detach().clone(),
               rho=coeff[:, 4].detach().clone(), nu=nu.detach().clone(), mref=float(mref), horizon=horizon,
               arrival_offset_ns=offset, count=len(marks), last_observed=marks[-1].detach().clone(), facts=facts)
    post = operator.Posterior(result['logw'][0], result['mu'][0], result['sigma'][0], result['logz'][0], budget, ref)
    budget.tick()
    return post


def arrays(value):
    if type(value) is torch.Tensor:
        return value.detach().cpu().numpy().copy()
    if type(value) in (tuple, list):
        return [arrays(v) for v in value]
    if type(value) is dict:
        return {k: arrays(v) for k, v in value.items()}
    return value


class ScoringFailure(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.evidence = evidence


def checked_scores(post, target, reference):
    """One shared budget and retained independent/primary/parity rejection evidence."""
    budget = post.budget
    progress = dict(phase='independent_completion', independent_scores={}, primary_scores={}, errors={})
    try:
        budget.tick()
        independent = reference.complete(arrays(post.reference), budget)
        progress['independent_posterior'] = dict(log_weights=independent.logw.copy(), means=independent.mu.copy(),
                                                 scales=independent.sd.copy(), log_normalizer=independent.logz)
        progress['phase'] = 'independent_scores'
        expected = independent.scores(target, crosscheck=True, evidence=progress['independent_scores'])
        score = progress['primary_scores']
        progress['phase'] = 'primary_scores'
        score['mean'] = float(post.mean().detach())
        score['nll'] = float(post.nll(torch.tensor(target, dtype=torch.float64)).detach())
        score['crps'] = post.crps(target)
        score['pit'] = post.cdf(target)
        score['quantiles'] = {}
        for q in (.025, .1, .25, .5, .75, .9, .975):
            score['quantiles'][str(q)] = post.quantile(q)
        score['median'] = score['quantiles']['0.5']
        for level, lo, hi in ((50, .25, .75), (80, .1, .9), (95, .025, .975)):
            score['coverage_'+str(level)] = bool(score['quantiles'][str(lo)] <= target <= score['quantiles'][str(hi)])
        errors = progress['errors']
        progress['phase'] = 'parity'
        for k in ('mean', 'nll', 'crps', 'pit', 'median'):
            errors[k] = abs(score[k]-expected[k])
        errors['log_normalizer'] = abs(float(post.logz.detach())-independent.logz)
        errors['quantiles'] = {q: abs(v-expected['quantiles'][q]) for q, v in score['quantiles'].items()}
        need(all(math.isfinite(v) and v <= (1e-4 if k in ('mean', 'nll', 'log_normalizer') else 1e-6)
                 for k, v in errors.items() if k != 'quantiles'), 'independent_parity')
        need(all(math.isfinite(v) and v <= 1e-6 for v in errors['quantiles'].values()), 'quantile_parity')
        need(all(type(expected['coverage_'+str(k)]) is bool and score['coverage_'+str(k)] == expected['coverage_'+str(k)] for k in (50, 80, 95)), 'coverage_parity')
        budget.tick()
        score['diagnostics'] = dict(errors=errors, work=budget.record(), allpositive_only=True, law=LAW)
        return score
    except Exception as exc:
        progress.update(reason=type(exc).__name__+':'+str(exc)[:256], work=budget.record(),
                        rejected_numeric=arrays(getattr(exc, 'numeric_evidence', None)),
                        exception_evidence=arrays(getattr(exc, 'evidence', None)))
        raise ScoringFailure('numerical_scoring_incomplete', progress) from exc
