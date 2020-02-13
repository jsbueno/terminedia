
def combine_sig(func1, func2):
    """creates a dummy function with the attrs of func1, but with
    extra, KEYWORD_ONLY parameters from func2.
    To be used in decorators that add new keyword parameters as
    the "__wrapped__"
    """
    from inspect import signature, _empty as insp_empty, _ParameterKind as ParKind
    from itertools import groupby
    sig1 = signature(func1)
    sig2 = signature(func2)
    pars1 = dict(groupby(sig1.parameters.values(), key=lambda p: p.kind))

    pos_only = [f"{p.name}{':' + repr(p.annotation) if p.annotation != insp_empty else ''}{'=' + repr(p.default) if p.default != insp_empty else ''}" for p in pars1[ParKind.POSITIONAL_ONLY]]

    pos_or_keyword = [f"{p.name}{':' + repr(p.annotation) if p.annotation != insp_empty else ''}{'=' + repr(p.default) if p.default != insp_empty else ''}" for p in pars1[ParKind.POSITIONAL_ONLY]]

    var_positional = [p for p in pars1[ParKind.VAR_POSITIONAL]]

    KEYWORD_ONLY = [f"{p.name}{':' + repr(p.annotation) if p.annotation != insp_empty else ''}{'=' + repr(p.default) if p.default != insp_empty else ''}" for p in pars1[ParKind.KEYWORD_ONLY]]

    var_positional = [p for p in pars1[ParKind.VAR_KEYWORD]]
