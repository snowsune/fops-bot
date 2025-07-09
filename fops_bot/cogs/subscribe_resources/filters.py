def parse_filters(filter_string):
    """
    Given a filter string (space or comma separated), return (positive_filters, negative_filters) as sets.
    """
    positive_filters = set()
    negative_filters = set()
    if filter_string:
        # Accept both comma and space as separators
        filters = filter_string.replace(",", " ").split()
        for f in filters:
            f = f.strip()
            if not f:
                continue
            if f.startswith("-"):
                negative_filters.add(f[1:].lower())
            else:
                positive_filters.add(f.lower())
    return positive_filters, negative_filters
