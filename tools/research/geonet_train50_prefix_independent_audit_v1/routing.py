"""All-match literal batch routing; unknown families are never inferred."""


def route(nslc, rows):
    return [row['ordinal'] for row in rows
            if row['queryable'] and nslc[:3] == [row['network'], row['station'], row['location']]
            and nslc[3][:2] == row['prefix']]


def nominal_suffixes(family):
    if family == 'ENZ':
        return ('E', 'N', 'Z')
    if family == '12Z':
        return ('1', '2', 'Z')
    return None
