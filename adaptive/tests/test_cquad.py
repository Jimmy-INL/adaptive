# -*- coding: utf-8 -*-
from functools import partial
from operator import attrgetter

import numpy as np
import pytest
from ..learner import IntegratorLearner
from ..learner.integrator_learner import DivergentIntegralError
from .algorithm_4 import algorithm_4, f0, f7, f21, f24, f63, fdiv
from .algorithm_4 import DivergentIntegralError as A4DivergentIntegralError

eps = np.spacing(1)


def run_integrator_learner(f, a, b, tol, nr_points):
    learner = IntegratorLearner(f, bounds=(a, b), tol=tol)
    for _ in range(nr_points):
        points, _ = learner.choose_points(1)
        learner.add_data(points, map(learner.function, points))
    return learner


def equal_ival(ival, other, *, verbose=False):
    """Note: Implementing __eq__ breaks SortedContainers in some way."""
    if ival.depth_complete is None:
        if verbose:
            print('Interval {} is not complete.'.format(ival))
        return False

    slots = set(ival.__slots__).intersection(other.__slots__)
    same_slots = []
    for s in slots:
        a = getattr(ival, s)
        b = getattr(other, s)
        is_equal = np.allclose(a, b, rtol=0, atol=eps, equal_nan=True)
        if verbose and not is_equal:
            print('ival.{} - other.{} = {}'.format(s, s, a - b))
        same_slots.append(is_equal)

    return all(same_slots)


def equal_ivals(ivals, other, *, verbose=False):
    """Note: `other` is a list of ivals."""
    if len(ivals) != len(other):
        if verbose:
            print('len(ivals)={} != len(other)={}'.format(
                len(ivals), len(other)))
        return False

    ivals = [sorted(i, key=attrgetter('a')) for i in [ivals, other]]
    return all(equal_ival(ival, other_ival, verbose=verbose)
               for ival, other_ival in zip(*ivals))


def same_ivals(f, a, b, tol):
        igral, err, nr_points, ivals = algorithm_4(f, a, b, tol)

        learner = run_integrator_learner(f, a, b, tol, nr_points)

        # This will only show up if the test fails, anyway
        print('igral difference', learner.igral-igral,
              'err difference', learner.err - err)

        return equal_ivals(learner.ivals, ivals, verbose=True)


def test_cquad():
    for i, args in enumerate([[f0, 0, 3, 1e-5],
                              [f7, 0, 1, 1e-6],
                              [f21, 0, 1, 1e-3],
                              [f24, 0, 3, 1e-3]]):
        assert same_ivals(*args), 'Function {}'.format(i)


@pytest.mark.xfail
def test_machine_precision():
    f, a, b, tol = [partial(f63, alpha=0.987654321, beta=0.45), 0, 1, 1e-10]
    igral, err, nr_points, ivals = algorithm_4(f, a, b, tol)

    learner = run_integrator_learner(f, a, b, tol, nr_points)

    print('igral difference', learner.igral-igral,
          'err difference', learner.err - err)

    assert equal_ivals(learner.ivals, ivals, verbose=True)


def test_machine_precision2():
    f, a, b, tol = [partial(f63, alpha=0.987654321, beta=0.45), 0, 1, 1e-10]
    igral, err, nr_points, ivals = algorithm_4(f, a, b, tol)

    learner = run_integrator_learner(f, a, b, tol, nr_points)

    np.testing.assert_almost_equal(igral, learner.igral)
    np.testing.assert_almost_equal(err, learner.err)


def test_divergence():
    """This function should raise a DivergentIntegralError."""
    f, a, b, tol = fdiv, 0, 1, 1e-6
    with pytest.raises(A4DivergentIntegralError) as e:
        igral, err, nr_points, ivals = algorithm_4(f, a, b, tol)

    nr_points = e.value.nr_points

    with pytest.raises(DivergentIntegralError):
        run_integrator_learner(f, a, b, tol, nr_points)


def test_choosing_and_adding_points_one_by_one():
    learner = IntegratorLearner(f24, bounds=(0, 3), tol=1e-10)
    for _ in range(1000):
        xs, _ = learner.choose_points(1)
        for x in xs:
            learner.add_point(x, learner.function(x))


def test_choosing_and_adding_multiple_points_at_once():
    learner = IntegratorLearner(f24, bounds=(0, 3), tol=1e-10)
    xs, _ = learner.choose_points(33)
    for x in xs:
        learner.add_point(x, learner.function(x))


def test_adding_points_and_skip_one_point():
    learner = IntegratorLearner(f24, bounds=(0, 3), tol=1e-10)
    xs, _ = learner.choose_points(17)
    skip_x = xs[1]

    for x in xs:
        if x != skip_x:
            learner.add_point(x, learner.function(x))

    for i in range(1000):
        xs, _ = learner.choose_points(1)
        for x in xs:
            if x != skip_x:
                learner.add_point(x, learner.function(x))

    # Now add the point that was skipped
    learner.add_point(skip_x, learner.function(skip_x))

    # Create a learner with the same number of points, which should
    # give an identical igral value.
    learner2 = IntegratorLearner(f24, bounds=(0, 3), tol=1e-10)
    for i in range(1017):
        xs, _ = learner2.choose_points(1)
        for x in xs:
            learner2.add_point(x, learner2.function(x))

    np.testing.assert_almost_equal(learner.igral, learner2.igral)


def test_add_points_in_random_order(first_add_33=False):
    import scipy.integrate
    import random

    for f, a, b in ([f0, 0, 3],
                    [f21, 0, 1],
                    [f24, 0, 3],
                    [f7, 0, 1],
                    ):
        learner = IntegratorLearner(f, bounds=(a, b), tol=1e-10)
        if first_add_33:
            xs, _ = learner.choose_points(33)
            for x in xs:
                learner.add_point(x, f(x))

        xs, _ = learner.choose_points(10000)
        random.shuffle(xs)
        for x in xs:
            learner.add_point(x, f(x))
        # This should at least be the case
        scipy_igral = scipy.integrate.quad(f, a, b)[0]
        scipy_igral = algorithm_4(f, a, b, tol=1e-10)[0]
        assert abs(learner.igral - scipy_igral) < 0.01, f


def test_add_points_in_random_order2():
    test_add_points_in_random_order(first_add_33=True)


def test_approximating_intervals():
    import random
    learner = IntegratorLearner(f24, bounds=(0, 3), tol=1e-10)

    xs, _ = learner.choose_points(10000)
    random.shuffle(xs)
    for x in xs:
        learner.add_point(x, f24(x))

    ivals = sorted(learner.approximating_intervals, key=lambda l: l.a)
    for i in range(len(ivals)-1):
        assert ivals[i].b == ivals[i+1].a, (ivals[i], ivals[i+1])
