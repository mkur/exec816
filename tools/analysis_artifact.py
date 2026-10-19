"""Keep explicitly marked analysis images out of executable packages and media."""
MARKER = b'EXEC816-QED-ANALYSIS-ONLY-V1'


def reject_analysis(payload):
    if MARKER in payload:
        raise RuntimeError('Analysis-only image cannot be packaged or copied to media')
