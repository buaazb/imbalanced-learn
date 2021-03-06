"""Class to perform under-sampling based on one-sided selection method."""

# Authors: Guillaume Lemaitre <g.lemaitre58@gmail.com>
#          Christos Aridas
# License: MIT

from __future__ import division

from collections import Counter

import numpy as np

from sklearn.base import clone
from sklearn.neighbors import KNeighborsClassifier
from sklearn.utils import check_random_state, safe_indexing

from ..base import BaseCleaningSampler
from .tomek_links import TomekLinks
from ...utils import Substitution
from ...utils._docstring import _random_state_docstring


@Substitution(
    sampling_strategy=BaseCleaningSampler._sampling_strategy_docstring,
    random_state=_random_state_docstring)
class OneSidedSelection(BaseCleaningSampler):
    """Class to perform under-sampling based on one-sided selection method.

    Read more in the :ref:`User Guide <condensed_nearest_neighbors>`.

    Parameters
    ----------
    {sampling_strategy}

    return_indices : bool, optional (default=False)
        Whether or not to return the indices of the samples randomly
        selected from the majority class.

    {random_state}

    n_neighbors : int or object, optional (default=\
KNeighborsClassifier(n_neighbors=1))
        If ``int``, size of the neighbourhood to consider to compute the
        nearest neighbors. If object, an estimator that inherits from
        :class:`sklearn.neighbors.base.KNeighborsMixin` that will be used to
        find the nearest-neighbors.

    n_seeds_S : int, optional (default=1)
        Number of samples to extract in order to build the set S.

    n_jobs : int, optional (default=1)
        The number of threads to open if possible.

    ratio : str, dict, or callable
        .. deprecated:: 0.4
           Use the parameter ``sampling_strategy`` instead. It will be removed
           in 0.6.

    Notes
    -----
    The method is based on [1]_.

    Supports multi-class resampling. A one-vs.-one scheme is used when sampling
    a class as proposed in [1]_. For each class to be sampled, all samples of
    this class and the minority class are used during the sampling procedure.

    See
    :ref:`sphx_glr_auto_examples_under-sampling_plot_one_sided_selection.py`

    References
    ----------
    .. [1] M. Kubat, S. Matwin, "Addressing the curse of imbalanced training
       sets: one-sided selection," In ICML, vol. 97, pp. 179-186, 1997.

    Examples
    --------

    >>> from collections import Counter
    >>> from sklearn.datasets import make_classification
    >>> from imblearn.under_sampling import \
    OneSidedSelection # doctest: +NORMALIZE_WHITESPACE
    >>> X, y = make_classification(n_classes=2, class_sep=2,
    ... weights=[0.1, 0.9], n_informative=3, n_redundant=1, flip_y=0,
    ... n_features=20, n_clusters_per_class=1, n_samples=1000, random_state=10)
    >>> print('Original dataset shape %s' % Counter(y))
    Original dataset shape Counter({{1: 900, 0: 100}})
    >>> oss = OneSidedSelection(random_state=42)
    >>> X_res, y_res = oss.fit_sample(X, y)
    >>> print('Resampled dataset shape %s' % Counter(y_res))
    Resampled dataset shape Counter({{1: 495, 0: 100}})

    """

    def __init__(self,
                 sampling_strategy='auto',
                 return_indices=False,
                 random_state=None,
                 n_neighbors=None,
                 n_seeds_S=1,
                 n_jobs=1,
                 ratio=None):
        super(OneSidedSelection, self).__init__(
            sampling_strategy=sampling_strategy, ratio=ratio)
        self.random_state = random_state
        self.return_indices = return_indices
        self.n_neighbors = n_neighbors
        self.n_seeds_S = n_seeds_S
        self.n_jobs = n_jobs

    def _validate_estimator(self):
        """Private function to create the NN estimator"""
        if self.n_neighbors is None:
            self.estimator_ = KNeighborsClassifier(
                n_neighbors=1, n_jobs=self.n_jobs)
        elif isinstance(self.n_neighbors, int):
            self.estimator_ = KNeighborsClassifier(
                n_neighbors=self.n_neighbors, n_jobs=self.n_jobs)
        elif isinstance(self.n_neighbors, KNeighborsClassifier):
            self.estimator_ = clone(self.n_neighbors)
        else:
            raise ValueError('`n_neighbors` has to be a int or an object'
                             ' inhereited from KNeighborsClassifier.'
                             ' Got {} instead.'.format(type(self.n_neighbors)))

    def _sample(self, X, y):
        """Resample the dataset.

        Parameters
        ----------
        X : ndarray, shape (n_samples, n_features)
            Matrix containing the data which have to be sampled.

        y : ndarray, shape (n_samples, )
            Corresponding label for each sample in X.

        Returns
        -------
        X_resampled : ndarray, shape (n_samples_new, n_features)
            The array containing the resampled data.

        y_resampled : ndarray, shape (n_samples_new)
            The corresponding label of `X_resampled`

        idx_under : ndarray, shape (n_samples, )
            If `return_indices` is `True`, a boolean array will be returned
            containing the which samples have been selected.

        """
        self._validate_estimator()

        random_state = check_random_state(self.random_state)
        target_stats = Counter(y)
        class_minority = min(target_stats, key=target_stats.get)

        idx_under = np.empty((0, ), dtype=int)

        for target_class in np.unique(y):
            if target_class in self.sampling_strategy_.keys():
                # select a sample from the current class
                idx_maj = np.flatnonzero(y == target_class)
                idx_maj_sample = idx_maj[random_state.randint(
                    low=0,
                    high=target_stats[target_class],
                    size=self.n_seeds_S)]

                minority_class_indices = np.flatnonzero(y == class_minority)
                C_indices = np.append(minority_class_indices, idx_maj_sample)

                # create the set composed of all minority samples and one
                # sample from the current class.
                C_x = safe_indexing(X, C_indices)
                C_y = safe_indexing(y, C_indices)

                # create the set S with removing the seed from S
                # since that it will be added anyway
                idx_maj_extracted = np.delete(idx_maj, idx_maj_sample, axis=0)
                S_x = safe_indexing(X, idx_maj_extracted)
                S_y = safe_indexing(y, idx_maj_extracted)
                self.estimator_.fit(C_x, C_y)
                pred_S_y = self.estimator_.predict(S_x)

                S_misclassified_indices = np.flatnonzero(pred_S_y != S_y)
                idx_tmp = idx_maj_extracted[S_misclassified_indices]
                idx_under = np.concatenate(
                    (idx_under, idx_maj_sample, idx_tmp), axis=0)
            else:
                idx_under = np.concatenate(
                    (idx_under, np.flatnonzero(y == target_class)), axis=0)

        X_resampled = safe_indexing(X, idx_under)
        y_resampled = safe_indexing(y, idx_under)

        # apply Tomek cleaning
        tl = TomekLinks(
            sampling_strategy=self.sampling_strategy_, return_indices=True)
        X_cleaned, y_cleaned, idx_cleaned = tl.fit_sample(
            X_resampled, y_resampled)

        idx_under = safe_indexing(idx_under, idx_cleaned)
        if self.return_indices:
            return (X_cleaned, y_cleaned, idx_under)
        else:
            return X_cleaned, y_cleaned
