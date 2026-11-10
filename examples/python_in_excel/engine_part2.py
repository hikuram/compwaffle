def cw_draw_row(values_input, colors_input, shapes_input, hatches_input,
                basis_input, options_input):
    """One isolated figure, no title, text labels or category names in Python."""
    raw = _cw_nums(values_input)
    packed = _cw_nums(colors_input)
    corners = _cw_nums(shapes_input)
    hatch_codes = _cw_nums(hatches_input)
    basis = _cw_nums(basis_input)
    opts = _cw_nums(options_input)
    count = raw.size
    if packed.size != count or hatch_codes.size != count or basis.size != count or corners.size != 2*count:
        raise ValueError('component and setting array widths differ')
    if opts.size < 11:
        raise ValueError('missing global numeric settings')
    mode = int(opts[0]); ncols = int(opts[1])
    cell_w = _cw_setting(opts[2],1.0)
    cell_h = _cw_setting(opts[3],0.78)
    gap = _cw_setting(opts[4],0.12)
    value_per_cell = _cw_setting(opts[6],100)
    default_span = _cw_setting(opts[7],0.15)
    default_bend = _cw_setting(opts[8],_CW_ROUND)
    show_scale = int(_cw_setting(opts[9],0))
    canvas_cols = int(_cw_setting(opts[10],32))
    hatch_shift = _cw_hatch_shift(opts)
    if ncols < 1 or canvas_cols < 1 or cell_w <= 0 or cell_h <= 0 or gap < 0:
        raise ValueError('invalid waffle size settings')
    corners = corners.reshape(2,count)
    cells, amount_per_cell, displayed_total = _cw_fills(
        raw,mode=mode,ncols=ncols,value_per_cell=value_per_cell,ref_weights=basis)
    if mode == 0:
        canvas_cols = ncols
    elif len(cells) > canvas_cols:
        raise ValueError('composition exceeds canvas columns; increase K12')
    fig,ax=plt.subplots(figsize=(7.65,0.54 if not show_scale else 0.76),dpi=130)
    fig.patch.set_facecolor('white')
    ax.set_position([0.012, 0.23 if show_scale else 0.08,
                     0.976, 0.69 if show_scale else 0.84])
    pitch = cell_w+gap
    ax.set_xlim(-0.04,canvas_cols*pitch-gap+0.04)
    ax.set_ylim(-0.30 if show_scale else -0.05,cell_h+0.05)
    ax.axis('off')
    for i,seg in enumerate(cells):
        single = (len(seg)==1 and math.isclose(seg[0][1],0,abs_tol=1e-10)
                  and math.isclose(seg[0][2],1,abs_tol=1e-10))
        j=seg[0][0] if single else None
        span = _cw_setting(corners[0,j],default_span) if single else default_span
        bend = _cw_setting(corners[1,j],default_bend) if single else default_bend
        left=i*pitch
        path=_cw_path(left,0,cell_w,cell_h,span,bend)
        bg=PathPatch(path,facecolor='#EDF1F5',edgecolor='none',zorder=2)
        ax.add_patch(bg)
        for k,a,b in seg:
            hidx=int(_cw_setting(hatch_codes[k],0))
            hatch = _CW_HATCHES[hidx] if 0<=hidx<len(_CW_HATCHES) else ''
            rgb = _cw_rgb(packed[k])
            rect=Rectangle((left+a*cell_w,0),(b-a)*cell_w,cell_h,
                           facecolor=rgb,
                           edgecolor=_cw_tone_rgb(rgb,hatch_shift) if hatch else 'none',
                           linewidth=0,hatch=hatch or None,zorder=3)
            rect.set_clip_path(bg)
            ax.add_patch(rect)
        ax.add_patch(PathPatch(path,facecolor='none',edgecolor='white',linewidth=0.45,zorder=4))
    if show_scale:
        tick_count=min(canvas_cols, 100)
        step=max(1,math.ceil(tick_count/5))
        for i in range(0,tick_count+1,step):
            x=i*pitch
            ax.plot([x,x],[-0.05,-0.12],color='#667085',lw=0.4)
            ax.text(x,-0.16,f'{i*amount_per_cell:.4g}',ha='center',va='top',
                    fontsize=6,color='#4B5563')
    return fig


def cw_legend_swatch(color_input, shape_input, hatch_input, options_input):
    rgb=_cw_nums(color_input)[0]
    shape=_cw_nums(shape_input)
    hatch_code=int(_cw_setting(_cw_nums(hatch_input)[0],0))
    opts=_cw_nums(options_input)
    if opts.size < 11:
        raise ValueError('missing global numeric settings')
    hatch_shift=_cw_hatch_shift(opts)
    span=_cw_setting(shape[0],_cw_setting(opts[7],0.15))
    bend=_cw_setting(shape[1],_cw_setting(opts[8],_CW_ROUND))
    hatch = _CW_HATCHES[hatch_code] if 0 <= hatch_code < len(_CW_HATCHES) else ''
    fig,ax=plt.subplots(figsize=(0.38,0.38),dpi=100)
    fig.patch.set_facecolor('white')
    ax.set_position([0,0,1,1])
    path=_cw_path(0.04,0.04,0.92,0.92,span,bend)
    fill_rgb=_cw_rgb(rgb)
    ax.add_patch(PathPatch(path,facecolor=fill_rgb,
                           edgecolor=_cw_tone_rgb(fill_rgb,hatch_shift) if hatch else 'none',
                           linewidth=0,hatch=hatch or None))
    ax.set(xlim=(0,1),ylim=(0,1))
    ax.axis('off')
    return fig
