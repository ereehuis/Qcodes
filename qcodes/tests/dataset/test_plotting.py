import numpy as np
from hypothesis import given, example, assume
from hypothesis.strategies import text, sampled_from, floats, lists, data, \
    one_of, just

from qcodes.dataset.plotting import _make_rescaled_ticks_and_units, \
    _ENGINEERING_PREFIXES, _SI_UNITS


@given(param_name=text(min_size=1, max_size=10),
       param_label=text(min_size=0, max_size=15),
       scale=sampled_from(sorted(list(_ENGINEERING_PREFIXES.keys()))),
       unit=sampled_from(sorted(list(_SI_UNITS))),
       data_strategy=data()
       )
@example(param_name='huge_param',
         param_label='Larger than the highest scale',
         scale=max(list(_ENGINEERING_PREFIXES.keys())),
         unit='V',
         data_strategy=np.random.random((5,)) \
                       * 10 ** (3 + max(list(_ENGINEERING_PREFIXES.keys()))))
@example(param_name='small_param',
         param_label='Lower than the lowest scale',
         scale=min(list(_ENGINEERING_PREFIXES.keys())),
         unit='V',
         data_strategy=np.random.random((5,)) \
                       * 10 ** (-3 + min(list(_ENGINEERING_PREFIXES.keys()))))
def test_rescaled_ticks_and_units(scale, unit,
                                  param_name, param_label, data_strategy):
    if isinstance(data_strategy, np.ndarray):
        # No need to generate data, because it is being passed
        data_array = data_strategy
    else:
        # Generate actual data
        scale_upper_bound = 999.9999 * 10 ** scale
        scale_lower_bound = 10 ** scale
        data_array = np.array(data_strategy.draw(
                    lists(elements=one_of(
                        floats(max_value=scale_upper_bound,
                               min_value=-scale_upper_bound),
                        just(np.nan)
                    ), min_size=1)))

        data_array_not_nans = data_array[np.logical_not(np.isnan(data_array))]

        # data_array with nan values *only* is not supported
        assume(len(data_array_not_nans) > 0)

        # data_array has to contain at least one number within the scale of
        # interest (meaning absolute value of at least one number has to
        # be larger than the lowest value within the scale of interest)
        assume((scale_lower_bound < np.abs(data_array_not_nans)).any())

    data_dict = {
        'name': param_name,
        'label': param_label,
        'unit': unit,
        'data': data_array
    }

    ticks_formatter, label = _make_rescaled_ticks_and_units(data_dict)

    expected_prefix = _ENGINEERING_PREFIXES[scale]
    if param_label == '':
        assert f"{param_name} ({expected_prefix}{unit})" == label
    else:
        assert f"{param_label} ({expected_prefix}{unit})" == label

    assert '5' == ticks_formatter(5 / (10 ** (-scale)))
    assert '1' == ticks_formatter(1 / (10 ** (-scale)))
    # also test the fact that "{:g}" is used in ticks formatter function
    assert '2.12346' == ticks_formatter(2.123456789 / (10 ** (-scale)))


@given(param_name=text(min_size=1, max_size=10),
       param_label=text(min_size=1, max_size=15),
       unit=sampled_from(['', 'unit', 'kg', '%', 'permille', 'nW']),
       data_array=lists(elements=floats(allow_nan=True), min_size=1)
       )
def test_rescaled_ticks_and_units_for_non_si_unit(
        unit, param_name, param_label, data_array):
    data_dict = {
        'name': param_name,
        'label': param_label,
        'unit': unit,
        'data': np.array(data_array)
    }

    ticks_formatter, label = _make_rescaled_ticks_and_units(data_dict)

    assert ticks_formatter is None
    assert label is None

