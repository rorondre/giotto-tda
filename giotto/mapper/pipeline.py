"""Construct and handle Mapper pipelines."""
# License: GNU AGPLv3

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from .cluster import ParallelClustering
from .nerve import Nerve
from .utils._list_feature_union import ListFeatureUnion
from .utils.pipeline import func_from_callable_on_rows, identity


global_pipeline_params = ('memory', 'verbose')
nodes_params = ('scaler', 'filter_func', 'cover')
clust_prepr_params = ('clustering_preprocessing',)
clust_params = ('clusterer', 'parallel_clustering_n_jobs',
                'parallel_clustering_prefer')
nerve_params = ('min_intersection',)
clust_prepr_params_prefix = 'pullback_cover__'
nodes_params_prefix = 'pullback_cover__map_and_cover__'
clust_params_prefix = 'clustering__'
nerve_params_prefix = 'nerve__'


class MapperPipeline(Pipeline):
    """Subclass of :class:`sklearn.pipeline.Pipeline` to deal with
    pipelines generated by :func:`make_mapper_pipeline`.

    The :meth:`set_params` method is modified from the corresponding method in
    :class:`sklearn.pipeline.Pipeline` to allow for simple access to the
    parameters involved in the definition of the Mapper algorithm, without the
    need to interface with the nested structure of the Pipeline objects
    generated by :func:`make_mapper_pipeline`. The convenience method
    :meth:`get_mapper_params` shows which parameters can be set. See the
    Examples below.

    Examples
    --------
    >>> from sklearn.cluster import DBSCAN
    >>> from sklearn.decomposition import PCA
    >>> from giotto.mapper import make_mapper_pipeline, CubicalCover
    >>> filter_func = PCA(n_components=2)
    >>> cover = CubicalCover()
    >>> clusterer = DBSCAN()
    >>> pipe = make_mapper_pipeline(filter_func=filter_func,
    ...                             cover=cover,
    ...                             clusterer=clusterer)
    >>> print(pipe.get_mapper_params()['clusterer__eps'])
    0.5
    >>> pipe.set_params(clusterer___eps=0.1)
    >>> print(pipe.get_mapper_params()['clusterer__eps'])
    0.1

    See also
    --------
    make_mapper_pipeline

    """

    # TODO abstract away common logic into a more generalisable implementation
    def get_mapper_params(self, deep=True):
        """Get all Mapper parameters for this estimator.

        Parameters
        ----------
        deep : boolean, optional, default: ``True``
            If ``True``, will return the parameters for this estimator and
            contained subobjects that are estimators.

        Returns
        -------
        params : mapping of string to any
            Parameter names mapped to their values.

        """
        pipeline_params = super().get_params(deep=deep)
        return {**{param: pipeline_params[param]
                   for param in global_pipeline_params},
                **self._clean_dict_keys(pipeline_params, nodes_params_prefix),
                **self._clean_dict_keys(
                    pipeline_params, clust_prepr_params_prefix),
                **self._clean_dict_keys(pipeline_params, clust_params_prefix),
                **self._clean_dict_keys(pipeline_params, nerve_params_prefix)}

    def set_params(self, **kwargs):
        """Set the Mapper parameters.

        Valid parameter keys can be listed with :meth:`get_mapper_params()`.

        Returns
        -------
        self

        """
        mapper_nodes_kwargs = self._subset_kwargs(kwargs, nodes_params)
        mapper_clust_prepr_kwargs = \
            self._subset_kwargs(kwargs, clust_prepr_params)
        mapper_clust_kwargs = self._subset_kwargs(kwargs, clust_params)
        mapper_nerve_kwargs = self._subset_kwargs(kwargs, nerve_params)
        if mapper_nodes_kwargs:
            super().set_params(
                **{nodes_params_prefix + key: mapper_nodes_kwargs[key]
                   for key in mapper_nodes_kwargs})
            [kwargs.pop(key) for key in mapper_nodes_kwargs]
        if mapper_clust_prepr_kwargs:
            super().set_params(
                **{clust_prepr_params_prefix + key:
                    mapper_clust_prepr_kwargs[key] for key in
                   mapper_clust_prepr_kwargs})
            [kwargs.pop(key) for key in mapper_clust_prepr_kwargs]
        if mapper_clust_kwargs:
            super().set_params(
                **{clust_params_prefix + key: mapper_clust_kwargs[key]
                   for key in mapper_clust_kwargs})
            [kwargs.pop(key) for key in mapper_clust_kwargs]
        if mapper_nerve_kwargs:
            super().set_params(
                **{nerve_params_prefix + key: mapper_nerve_kwargs[key]
                   for key in mapper_nerve_kwargs})
            [kwargs.pop(key) for key in mapper_nerve_kwargs]
        super().set_params(**kwargs)
        return self

    @staticmethod
    def _subset_kwargs(kwargs, param_strings):
        return {key: value for key, value in kwargs.items()
                if key.startswith(param_strings)}

    @staticmethod
    def _clean_dict_keys(kwargs, prefix):
        return {
            key[len(prefix):]: kwargs[key]
            for key in kwargs
            if (key.startswith(prefix)
                and not key.startswith(prefix + 'steps')
                and not key.startswith(prefix + 'memory')
                and not key.startswith(prefix + 'verbose')
                and not key.startswith(prefix + 'transformer_list')
                and not key.startswith(prefix + 'n_jobs')
                and not key.startswith(prefix + 'transformer_weights')
                and not key.startswith(prefix + 'map_and_cover'))
        }


def make_mapper_pipeline(scaler=None,
                         filter_func=None,
                         cover=None,
                         clustering_preprocessing=None,
                         clusterer=None,
                         parallel_clustering_n_jobs=None,
                         parallel_clustering_prefer='threads',
                         min_intersection=1,
                         memory=None,
                         verbose=False):
    """Construct a MapperPipeline object according to the specified Mapper
    steps.

    All steps may be arbitrary scikit-learn Pipeline objects. The scaling
    and cover steps must be transformers implementing a ``fit_transform``
    method. The filter function step may be a transformer implementing a
    ``fit_transform``, or a callable acting on one-dimensional arrays -- in
    the latter case, a transformer is internally created whose
    ``fit_transform`` applies this callable independently on each row of the
    data. The clustering step need only implement a ``fit`` method storing
    clustering labels.

    Parameters
    ----------
    scaler : object or None, optional, default: ``None``
        Scaling transformer. If ``None``, no scaling is performed.

    filter_func : object, callable or None, optional, default: ``None``
        Filter function to apply to the scaled data. ``None`` means using PCA
        (:meth:`sklearn.decomposition.PCA`) with 2 components.

    cover : object or None, optional, default: ``None``
        Covering transformer.``None`` means using a cubical cover
        (:meth:`giotto.mapper.CubicalCover`) with its default parameters.

    clustering_preprocessing : object or None, optional, default: ``None``
        If not ``None``, it is a transformer which is applied to the
        data independently to the `scaler` -> `filter_func` -> cover` pipeline.
        Clustering is then performed on portions (determined by the `scaler`
        -> `filter_func` -> cover` pipeline) of the transformed data.

    clusterer : object or None, optional, default: ``None``
        Clustering object. ``None`` means using DBSCAN
        (:meth:`sklearn.cluster.DBSCAN`) with its default parameters.

    parallel_clustering_n_jobs : int or None, optional, default: ``None``
        The number of jobs to use in a joblib-parallel application of the
        clustering step across pullback cover sets. ``None`` means 1 unless
        in a :obj:`joblib.parallel_backend` context. ``-1`` means using all
        processors.

    parallel_clustering_prefer : ``'processes'`` | ``'threads'``, optional, \
        default: ``'threads'``
        Selects the default joblib backend to use in a joblib-parallel
        application of the clustering step across pullback cover sets.
        The default process-based backend is 'loky' and the default
        thread-based backend is 'threading'. See [1]_.

    min_intersection : int, optional, default: ``1``
        Minimum size of the intersection between clusters required for
        creating an edge in the Mapper graph.

    memory : None, str or object with the joblib.Memory interface, \
        optional, default: ``None``
        Used to cache the fitted transformers of the pipeline. By default, no
        caching is performed. If a string is given, it is the path to the
        caching directory. Enabling caching triggers a clone of the
        transformers before fitting. Therefore, the transformer instance
        given to the pipeline cannot be inspected directly. Use the attribute
        ``named_steps`` or ``steps`` to inspect estimators within the
        pipeline. Caching the transformers is advantageous when fitting is
        time consuming.

    verbose : bool, optional, default: ``False``
        If True, the time elapsed while fitting each step will be printed as it
        is completed.

    Returns
    -------
    mapper_pipeline : :class:`MapperPipeline` object
        Output Mapper pipeline.

    Examples
    --------
    >>> # Example of basic usage with default parameters
    >>> from giotto.mapper import make_mapper_pipeline
    >>> mapper = make_mapper_pipeline()
    >>> print(mapper.__class__)
    <class 'giotto.mapper.pipeline.MapperPipeline'>
    >>> mapper_params = mapper.get_mapper_params()
    >>> print(mapper_params['filter_func'].__class__)
    <class 'sklearn.decomposition._pca.PCA'>
    >>> print(mapper_params['cover'].__class__)
    <class 'giotto.mapper.cover.CubicalCover'>
    >>> print(mapper_params['clusterer'].__class__)
    <class 'sklearn.cluster._dbscan.DBSCAN'>
    >>> X = np.random.random((10000, 4))  # 10000 points in 4-dimensional space
    >>> mapper_graph = mapper.fit_transform(X)  # Create the mapper graph
    >>> print(type(mapper_graph))
    igraph.Graph
    >>> #######################################################################
    >>> # Example using a scaler from scikit-learn, a filter function from
    >>> # giotto.mapper.filter, and a clusterer from giotto.mapper.cluster
    >>> from sklearn.preprocessing import MinMaxScaler
    >>> from giotto.mapper import Projection, FirstHistogramGap
    >>> scaler = MinMaxScaler()
    >>> filter_func = Projection(columns=[0, 1])
    >>> clusterer = FirstHistogramGap()
    >>> mapper = make_mapper_pipeline(scaler=scaler,
    ...                               filter_func=filter_func,
    ...                               clusterer=clusterer)
    >>> #######################################################################
    >>> # Example using a callable acting on each row of X separately
    >>> import numpy as np
    >>> from giotto.mapper import OneDimensionalCover
    >>> cover = OneDimensionalCover()
    >>> mapper.set_params(scaler=None, filter_func=np.sum, cover=cover)
    >>> #######################################################################
    >>> # Example setting the memory parameter to cache each step and avoid
    >>> # recomputation of early steps
    >>> from tempfile import mkdtemp
    >>> from shutil import rmtree
    >>> cachedir = mkdtemp()
    >>> mapper.set_params(memory=cachedir, verbose=True)
    >>> mapper_graph = mapper.fit_transform(X)
    [Pipeline] ............ (step 1 of 3) Processing scaler, total=   0.0s
    [Pipeline] ....... (step 2 of 3) Processing filter_func, total=   0.0s
    [Pipeline] ............. (step 3 of 3) Processing cover, total=   0.0s
    [Pipeline] .... (step 1 of 3) Processing pullback_cover, total=   0.0s
    [Pipeline] ........ (step 2 of 3) Processing clustering, total=   0.3s
    [Pipeline] ............. (step 3 of 3) Processing nerve, total=   0.0s
    >>> mapper.set_params(min_intersection=3)
    >>> mapper_graph = mapper.fit_transform(X)
    [Pipeline] ............. (step 3 of 3) Processing nerve, total=   0.0s
    >>> # Clear the cache directory when you don't need it anymore
    >>> rmtree(cachedir)
    >>> #######################################################################
    >>> # Example using a large dataset for which parallelism in
    >>> # clustering across the pullback cover sets can be beneficial
    >>> from sklearn.cluster import DBSCAN
    >>> mapper = make_mapper_pipeline(clusterer=DBSCAN(),
    ...                               parallel_clustering_n_jobs=6,
    ...                               memory=mkdtemp(),
    ...                               verbose=True)
    >>> X = np.random.random((100000, 4))
    >>> mapper.fit_transform(X)
    [Pipeline] ............ (step 1 of 3) Processing scaler, total=   0.0s
    [Pipeline] ....... (step 2 of 3) Processing filter_func, total=   0.1s
    [Pipeline] ............. (step 3 of 3) Processing cover, total=   0.6s
    [Pipeline] .... (step 1 of 3) Processing pullback_cover, total=   0.7s
    [Pipeline] ........ (step 2 of 3) Processing clustering, total=   1.9s
    [Pipeline] ............. (step 3 of 3) Processing nerve, total=   0.3s
    >>> mapper.set_params(parallel_clustering_n_jobs=1)
    >>> mapper.fit_transform(X)
    [Pipeline] ........ (step 2 of 3) Processing clustering, total=   5.3s
    [Pipeline] ............. (step 3 of 3) Processing nerve, total=   0.3s

    See also
    --------
    MapperPipeline, giotto.mapper.utils.decorators.method_to_transform

    References
    ----------
    .. [1] "Thread-based parallelism vs process-based parallelism", in
           `joblib documentation
           <https://joblib.readthedocs.io/en/latest/parallel.html>`_.

    """

    if scaler is None:
        _scaler = identity(validate=False)
    else:
        _scaler = scaler

    # If filter_func is not a scikit-learn transformer, hope it as a
    # callable to be applied on each row separately. Then attempt to create a
    # FunctionTransformer object to implement this behaviour.
    if filter_func is None:
        from sklearn.decomposition import PCA
        _filter_func = PCA(n_components=2)
    elif not hasattr(filter_func, 'fit_transform'):
        _filter_func = func_from_callable_on_rows(filter_func)
        _filter_func = FunctionTransformer(func=_filter_func, validate=True)
    else:
        _filter_func = filter_func

    if cover is None:
        from .cover import CubicalCover
        _cover = CubicalCover()
    else:
        _cover = cover

    if clustering_preprocessing is None:
        _clustering_preprocessing = identity(validate=True)
    else:
        _clustering_preprocessing = clustering_preprocessing

    if clusterer is None:
        from sklearn.cluster import DBSCAN
        _clusterer = DBSCAN()
    else:
        _clusterer = clusterer

    map_and_cover = Pipeline(
        steps=[('scaler', _scaler),
               ('filter_func', _filter_func),
               ('cover', _cover)],
        verbose=verbose)

    all_steps = [
        ('pullback_cover', ListFeatureUnion(
            [('clustering_preprocessing', _clustering_preprocessing),
             ('map_and_cover', map_and_cover)])),
        ('clustering', ParallelClustering(
            clusterer=_clusterer,
            parallel_clustering_n_jobs=parallel_clustering_n_jobs,
            parallel_clustering_prefer=parallel_clustering_prefer)),
        ('nerve', Nerve(min_intersection=min_intersection))
    ]

    mapper_pipeline = MapperPipeline(
        steps=all_steps, memory=memory, verbose=verbose)
    return mapper_pipeline
