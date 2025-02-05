###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2021, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#          http://ilastik.org/license.html
###############################################################################
import logging

from ilastik.config import runtime_cfg
from ilastik.applets.serverConfiguration.types import ServerConfig, Device
from ._nnWorkflowBase import _NNWorkflowBase
from ._localLauncher import LocalServerLauncher
from ilastik.applets.neuralNetwork import NNClassApplet
from lazyflow.operators import tiktorch


logger = logging.getLogger(__name__)


class LocalWorkflow(_NNWorkflowBase):
    """
    This class provides workflow for a local tiktorch executable.
    It can be specified via "--tiktorch_executable" command line parameter.
    Furthermore, the ilastik app will try to find a tiktorch version
    (usually the case when bundled for distribution) if the parameter is not
    supplied. If it cannot be found, workflow is not available.
    """

    auto_register = False
    workflowName = "Neural Network Classification (Local)"
    workflowDescription = "Allows to apply bioimage.io models on your data using bundled tiktorch"

    def __init__(self, shell, headless, workflow_cmdline_args, project_creation_args, *args, **kwargs):
        tiktorch_exe_path = runtime_cfg.tiktorch_executable
        if not tiktorch_exe_path:
            raise RuntimeError("No tiktorch-executable specified")

        self._launcher = LocalServerLauncher(tiktorch_exe_path)
        super().__init__(shell, headless, workflow_cmdline_args, project_creation_args, *args, **kwargs)

    def _createClassifierApplet(self):
        conn_str = self._launcher.start()
        srv_config = ServerConfig(id="auto", address=conn_str, devices=[Device(id="cpu", name="cpu", enabled=True)])
        connFactory = tiktorch.TiktorchConnectionFactory()
        conn = connFactory.ensure_connection(srv_config)

        devices = conn.get_devices()
        preferred_cuda_device_id = runtime_cfg.preferred_cuda_device_id
        device_ids = [dev[0] for dev in devices]
        cuda_devices = tuple(d for d in device_ids if d.startswith("cuda"))

        if preferred_cuda_device_id not in device_ids:
            if preferred_cuda_device_id:
                logger.warning(f"Could nor find preferred cuda device {preferred_cuda_device_id}")
            try:
                preferred_cuda_device_id = cuda_devices[0]
            except IndexError:
                preferred_cuda_device_id = "cpu"

            logger.info(f"Using default device for Neural Network Workflow {preferred_cuda_device_id}")
        else:
            logger.info(f"Using specified device for Neural Netowrk Workflow {preferred_cuda_device_id}")

        device_name = devices[device_ids.index(preferred_cuda_device_id)][1]

        srv_config = srv_config.evolve(devices=[Device(id=preferred_cuda_device_id, name=device_name, enabled=True)])

        self.nnClassificationApplet = NNClassApplet(self, "NNClassApplet", connectionFactory=connFactory)
        opClassify = self.nnClassificationApplet.topLevelOperator
        opClassify.ServerConfig.setValue(srv_config)
        self._applets.append(self.nnClassificationApplet)

    def cleanUp(self):
        super().cleanUp()
        self._launcher.stop()
