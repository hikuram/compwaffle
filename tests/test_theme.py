from importlib.resources import files
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from compwaffle import waffle, WaffleStyle
from compwaffle.theme import is_dark, adapt_cell_style


def test_paper_and_dark_mplstyle_bundled():
    styles = files('compwaffle').joinpath('stylelib')
    assert styles.joinpath('paper.mplstyle').is_file()
    assert styles.joinpath('dark.mplstyle').is_file()
    with plt.style.context(str(styles.joinpath('dark.mplstyle'))):
        assert is_dark()
        adapted = adapt_cell_style(WaffleStyle())
        assert adapted.empty_color != WaffleStyle().empty_color
        fig, _ = waffle({'A': 72.5, 'B': 27.5}, title='Dark example')
        fig.canvas.draw()
        plt.close(fig)
    with plt.style.context(str(styles.joinpath('paper.mplstyle'))):
        assert not is_dark()
