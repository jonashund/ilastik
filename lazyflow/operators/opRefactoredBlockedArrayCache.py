###############################################################################
#   lazyflow: data flow based lazy parallel computation framework
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#          http://ilastik.org/license/
###############################################################################

from lazyflow.graph import Operator, InputSlot, OutputSlot

from opCacheFixer import OpCacheFixer
from opUnblockedArrayCache import OpUnblockedArrayCache
from opSplitRequestsBlockwise import OpSplitRequestsBlockwise

class OpRefactoredBlockedArrayCache(Operator):
    """
    A blockwise array cache designed to replace the old OpBlockedArrayCache.  
    Instead of a monolithic implementation, this operator is a small pipeline of three simple operators.
    
    The actual caching of data is handled by an unblocked cache, so the "blocked" functionality is 
    implemented via separate "splitting" operator that comes after the cache.
    Also, the "fixAtCurrent" feature is implemented in a special operator, which comes before the cache.    
    """
    Input = InputSlot(allow_mask=True)
    fixAtCurrent = InputSlot(value=False)
    #BlockShape = InputSlot()
    innerBlockShape = InputSlot(optional=True)
    outerBlockShape = InputSlot()
    
    Output = OutputSlot(allow_mask=True)
    
    def __init__(self, *args, **kwargs):
        super( OpRefactoredBlockedArrayCache, self ).__init__(*args, **kwargs)
        
        # Input ---------> opCacheFixer -> opUnblockedArrayCache -> opSplitRequestsBlockwise -> Output
        #                 /                                        /
        # fixAtCurrent --                                         /
        #                                                        /
        # BlockShape --------------------------------------------
        
        self._opCacheFixer = OpCacheFixer( parent=self )
        self._opCacheFixer.Input.connect( self.Input )
        self._opCacheFixer.fixAtCurrent.connect( self.fixAtCurrent )

        self._opUnblockedArrayCache = OpUnblockedArrayCache( parent=self )
        self._opUnblockedArrayCache.Input.connect( self._opCacheFixer.Output )

        self._opSplitRequestsBlockwise = OpSplitRequestsBlockwise( always_request_full_blocks=True, parent=self )
        self._opSplitRequestsBlockwise.BlockShape.connect( self.outerBlockShape )
        self._opSplitRequestsBlockwise.Input.connect( self._opUnblockedArrayCache.Output )

        # FIXME: Connecting the output directly like this will result in RAM being allocated for zero-blocks in the cache when fixAtCurrent=True.
        #        It doesn't result in incorrect results, but it is inefficient.
        self.Output.connect( self._opSplitRequestsBlockwise.Output )
        
    def setupOutputs(self):
        pass

    def execute(self, slot, subindex, roi, result):
        assert False, "Shouldn't get here."

    def propagateDirty(self, slot, subindex, roi):
        pass
