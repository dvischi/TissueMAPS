# Copyright (C) 2016 University of Zurich.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''Jterator module for measuring point pattern of objects within parent objects.
'''
import collections
import mahotas as mh

import jtlib.features


VERSION = '0.1.1'

Output = collections.namedtuple('Output', ['measurements', 'figure'])


def main(extract_objects, ref_objects, assign_objects, aggregate, plot=False):
    '''Measures point pattern features for objects in `extract_objects`
    within `ref_objects` and assign them to `assign_objects`.

    Parameters
    ----------
    extract_objects: numpy.ndarray[int32]
        label image with objects for which features should be extracted
    ref_objects: numpy.ndarray[int32]
        label image with objects relative to which pattern should be assessed
        (`ref_objects` must contain `extract_objects`)
    assign_objects: numpy.ndarray[int32]
        label image with objects to which extracted features should be assigned
    aggregate: bool, optional
        whether measurements should be aggregated in case `extract_objects`
        and `assign_objects` have a many-to-one relationship
    plot: bool, optional
        whether a plot should be generated (default: ``False``)

    Returns
    -------
    jtmodules.measure_point_pattern.Output[Union[List[pandas.DataFrame], str]]

    See also
    --------
    :class:`jtlib.features.PointPattern`

    '''
    f = jtlib.features.PointPattern(
        label_image=extract_objects, parent_label_image=ref_objects
    )

    f.check_assignment(assign_objects, aggregate)

    if aggregate:
        measurements = [f.extract_aggregate(assign_objects)]
    else:
        measurements = [f.extract()]

    if plot:
        figure = f.plot()
    else:
        figure = str()

    return Output(measurements, figure)

