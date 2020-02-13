
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
        pars1 = {group:list(params)  for group, params in groupby(sig1.parameters.values(), key=lambda p: p.kind)}
        pars2 = {group:list(params)  for group, params in groupby(sig2.parameters.values(), key=lambda p: p.kind)}

        def render_annotation(p):
            return f"{':' + (repr(p.annotation) if not isinstance(p.annotation, type) else repr(p.annotation.__name__)) if p.annotation != insp_empty else ''}"

        def render_params(p):
            return f"{'=' + repr(p.default) if p.default != insp_empty else ''}"

        pos_only = [f"{p.name}{render_annotation(p)}{render_params(p)}" for p in pars1[ParKind.POSITIONAL_ONLY]]

        pos_or_keyword = [f"{p.name}{render_annotation(p)}{render_params(p)}" for p in pars1[ParKind.POSITIONAL_OR_KEYWORD]]

        var_positional = [p for p in pars1[ParKind.VAR_POSITIONAL]]

        keyword_only = [f"{p.name}{render_annotation(p)}{render_params(p)}" for p in pars1[ParKind.KEYWORD_ONLY]]

        var_keyword = [p for p in pars1[ParKind.VAR_KEYWORD]]

        extra_parameters = [f"{p.name}{render_annotation(p)}{render_params(p)}" for p in pars2[ParKind.KEYWORD_ONLY]]

        paramspec = ', '.join((
            ', '.join(pos_only),
            *(['/'] if pos_only else []),
            ', '.join(pos_or_keyword),
            *(['*' if not var_positional else f"*{var_positional[0].name}"] if keyword_only or extra_parameters else []),
            ", ".join(keyword_only),
            ", ".join(extra_parameters),
            *([f"**{var_keyword[0].name}"] if var_keyword else [])
        ))

        declaration = f"def {func1.__name__}({paramspec}): pass"

        f_globals = func1.__globals__

        f_locals = {}

        exec(declaration, f_globals, f_locals)

        result = f_locals[func1.__name__]
        result.__qualname__ = func1.__qualname__
        result.__doc__ = func1.__doc__

        return result
