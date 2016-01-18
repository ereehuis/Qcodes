'''
Live plotting in Jupyter notebooks
using the nbagg backend and matplotlib
'''
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
import numpy as np
from numpy.ma import masked_invalid, getmask
from collections import Mapping

from .base import BasePlot


class MatPlot(BasePlot):
    '''
    Plot x/y lines or x/y/z heatmap data. The first trace may be included
    in the constructor, other traces can be added with MatPlot.add()

    args: shortcut to provide the x/y/z data. See MatPlot.add

    figsize: (width, height) tuple to pass to plt.figure
        default (12, 5)
    interval: period in seconds between update checks

    subplots: either a sequence (args) or mapping (kwargs) to pass to
        plt.subplots. default is a single simple subplot (1, 1)
        you can use this to pass kwargs to the plt.figure constructor

    kwargs: passed along to MatPlot.add() to add the first data trace
    '''
    def __init__(self, *args, figsize=(8, 5), interval=1, subplots=(1, 1),
                 **kwargs):

        super().__init__(interval)

        if isinstance(subplots, Mapping):
            self.fig, self.subplots = plt.subplots(figsize=figsize, **subplots)
        else:
            self.fig, self.subplots = plt.subplots(*subplots, figsize=figsize)
        if not hasattr(self.subplots, '__len__'):
            self.subplots = (self.subplots,)

        self.title = self.fig.suptitle('')

        if args or kwargs:
            self.add(*args, **kwargs)

    def add_to_plot(self, **kwargs):
        '''
        adds one trace to this MatPlot.

        kwargs: with the following exceptions (mostly the data!), these are
            passed directly to the matplotlib plotting routine.

            `subplot`: the 1-based axes number to append to (default 1)

            if kwargs include `z`, we will draw a heatmap (ax.pcolormesh):
                `x`, `y`, and `z` are passed as positional args to pcolormesh

            without `z` we draw a scatter/lines plot (ax.plot):
                `x`, `y`, and `fmt` (if present) are passed as positional args
        '''
        # TODO some way to specify overlaid axes?

        ax = self._get_axes(kwargs)
        if 'z' in kwargs:
            plot_object = self._draw_pcolormesh(ax, **kwargs)
        else:
            plot_object = self._draw_plot(ax, **kwargs)

        self._update_labels(ax, kwargs)
        prev_default_title = self.get_default_title()

        self.traces.append({
            'config': kwargs,
            'plot_object': plot_object
        })

        if prev_default_title == self.title.get_text():
            # in case the user has updated title, don't change it anymore
            self.title.set_text(self.get_default_title())

    def _get_axes(self, config):
        return self.subplots[config.get('subplot', 1) - 1]

    def set_title(self, title):
        self.title.set_text(title)

    def _update_labels(self, ax, config):
        if 'x' in config and not ax.get_xlabel():
            ax.set_xlabel(self.get_label(config['x']))
        if 'y' in config and not ax.get_ylabel():
            ax.set_ylabel(self.get_label(config['y']))

    def update_plot(self):
        '''
        update the plot. The DataSets themselves have already been updated
        in update, here we just push the changes to the plot.
        '''
        # matplotlib doesn't know how to autoscale to a pcolormesh after the
        # first draw (relim ignores it...) so we have to do this ourselves
        bboxes = dict(zip(self.subplots, [[] for p in self.subplots]))

        for trace in self.traces:
            config = trace['config']
            plot_object = trace['plot_object']
            if 'z' in config:
                # pcolormesh doesn't seem to allow editing x and y data, only z
                # so instead, we'll remove and re-add the data.
                if plot_object:
                    plot_object.remove()

                ax = self._get_axes(config)
                plot_object = self._draw_pcolormesh(ax, **config)
                trace['plot_object'] = plot_object

                if plot_object:
                    bboxes[plot_object.axes].append(
                        plot_object.get_datalim(plot_object.axes.transData))
            else:
                for axletter in 'xy':
                    setter = 'set_' + axletter + 'data'
                    if axletter in config:
                        getattr(plot_object, setter)(config[axletter])

        for ax in self.subplots:
            if ax.get_autoscale_on():
                ax.relim()
                if bboxes[ax]:
                    bbox = Bbox.union(bboxes[ax])
                    if np.all(np.isfinite(ax.dataLim)):
                        # should take care of the case of lines + heatmaps
                        # where there's already a finite dataLim from relim
                        ax.dataLim.set(Bbox.union(ax.dataLim, bbox))
                    else:
                        # when there's only a heatmap, relim gives inf bounds
                        # so just completely overwrite it
                        ax.dataLim = bbox
                ax.autoscale()

        self.fig.canvas.draw()

    def _draw_plot(self, ax, y, x=None, fmt=None, subplot=1, **kwargs):
        # subplot=1 is just there to strip this out of kwargs
        args = [arg for arg in [x, y, fmt] if arg is not None]
        return ax.plot(*args, **kwargs)[0]

    def _draw_pcolormesh(self, ax, z, x=None, y=None, subplot=1, **kwargs):
        args = [masked_invalid(arg) for arg in [x, y, z]
                if arg is not None]

        for arg in args:
            if np.all(getmask(arg)):
                # if any entire array is masked, don't draw at all
                # there's nothing to draw, and anyway it throws a warning
                return False

        pc = ax.pcolormesh(*args, **kwargs)

        if getattr(ax, 'qcodes_colorbar', None):
            # update_normal doesn't seem to work...
            ax.qcodes_colorbar.update_bruteforce(pc)
        else:
            # TODO: what if there are several colormeshes on this subplot,
            # do they get the same colorscale?
            # We should make sure they do, and have it include
            # the full range of both.
            ax.qcodes_colorbar = self.fig.colorbar(pc, ax=ax)

            # ideally this should have been in _update_labels, but
            # the colorbar doesn't necessarily exist there.
            # I guess we could create the colorbar no matter what,
            # and just give it a dummy mappable to start, so we could
            # put this where it belongs.
            ax.qcodes_colorbar.set_label(self.get_label(z))

        return pc
