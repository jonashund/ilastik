import warnings
from functools import singledispatch
import vigra
import numpy
import xarray

import numpy
import vigra
import xarray

from ilastik.applets.featureSelection.opFeatureSelection import OpFeatureSelection
from ilastik.experimental import parser
from lazyflow.graph import Graph
from lazyflow.operators import OpReorderAxes
from lazyflow.operators.classifierOperators import OpClassifierPredict

from .types import PixelClassificationPipeline


def _reorder_output(output: numpy.ndarray, output_axisorder: vigra.AxisTags, input_axisorder: str):
    assert len(output.shape) == len(output_axisorder)
    if "c" in output_axisorder and "c" not in input_axisorder:
        # if input data was supplied without channel axes, put channel last
        # output per default
        input_axisorder = input_axisorder + "c"

    drop_axes = []
    for axis, size in zip(output_axisorder, output.shape):
        if axis not in input_axisorder:
            assert size == 1
            drop_axes.append(axis)

    output_array = xarray.DataArray(output, dims=tuple(output_axisorder))
    return output_array.squeeze(drop_axes).transpose(*tuple(input_axisorder))


@singledispatch
def convert_to_vigra(data):
    raise NotImplementedError(f"{type(data)}")


@convert_to_vigra.register
def _(data: vigra.VigraArray):
    return data


@convert_to_vigra.register
def _(data: numpy.ndarray):
    raise ValueError("numpy arrays don't provide information about axistags expecting xarray")


@convert_to_vigra.register
def _(data: xarray.DataArray):
    axistags = "".join(data.dims)
    return vigra.taggedView(data.values, axistags)


class _PixelClassificationPipelineImpl(PixelClassificationPipeline):
    def __init__(self, project: parser.PixelClassificationProject):
        feature_matrix = project.feature_matrix
        classifer = project.classifier
        self._num_channels = project.data_info.num_channels
        self._axis_order = project.data_info.axis_order
        self._num_spatial_dims = len(project.data_info.spatial_axes)

        graph = Graph()
        self._reorder_op = OpReorderAxes(graph=graph, AxisOrder="tzyxc")

        self._feature_sel_op = OpFeatureSelection(graph=graph)
        self._feature_sel_op.InputImage.connect(self._reorder_op.Output)
        self._feature_sel_op.FeatureIds.setValue(feature_matrix.names)
        self._feature_sel_op.Scales.setValue(feature_matrix.scales)
        self._feature_sel_op.SelectionMatrix.setValue(feature_matrix.selections)
        self._feature_sel_op.ComputeIn2d.setValue(feature_matrix.compute_in_2d.tolist())

        self._predict_op = OpClassifierPredict(graph=graph)
        self._predict_op.Classifier.setValue(classifer.instance)
        self._predict_op.Classifier.meta.classifier_factory = classifer.factory
        self._predict_op.Image.connect(self._feature_sel_op.OutputImage)
        self._predict_op.LabelsCount.setValue(classifer.label_count)

    def predict(self, data):
        warnings.warn(
            "The predict method will disappear in future versions, please use get_probabilities()",
            DeprecationWarning,
        )
        return self.get_probabilities(raw_data=data)

    def _check_data(self, data):
        num_channels_in_data = data.channels
        if num_channels_in_data != self._num_channels:
            raise ValueError(
                f"Number of channels mismatch. Classifier trained for {self._num_channels} but input has {num_channels_in_data}"
            )

        num_spatial_in_data = sum(a.isSpatial() for a in data.axistags)
        if num_spatial_in_data != self._num_spatial_dims:
            raise ValueError(
                "Number of spatial dims doesn't match. "
                f"Classifier trained for {self._num_spatial_dims} but input has {num_spatial_in_data}"
            )

    def get_probabilities(self, raw_data):
        return self._process(raw_data, output_slot=self._predict_op.PMaps)

    def _process(self, raw_data, output_slot):
        raw_data = convert_to_vigra(raw_data)
        input_axistags = "".join(ax.key for ax in raw_data.axistags)
        self._check_data(raw_data)
        self._reorder_op.Input.setValue(raw_data)
        processed_data = output_slot.value[...]
        return _reorder_output(processed_data, "".join(output_slot.meta.axistags.keys()), input_axistags)


@singledispatch
def get_pipeline_for_project(project):
    raise NotImplementedError(f"{type(project)}")


@get_pipeline_for_project.register
def _(project: parser.PixelClassificationProject):
    return _PixelClassificationPipelineImpl(project=project)
