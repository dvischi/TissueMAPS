import json
import os.path as p
import logging

import numpy as np
from flask import jsonify, send_file, current_app, request
from flask.ext.jwt import jwt_required
from flask.ext.jwt import current_identity

import tmlib.workflow.registry
from tmlib.workflow.canonical import CanonicalWorkflowDescription
from tmlib.workflow.submission import SubmissionManager
from tmlib.workflow.tmaps.api import WorkflowManager
from tmlib.models import (
    Experiment, ChannelLayer, Plate, Acquisition, Feature, PyramidTileFile
)
from tmaps.util import (
    extract_model_from_path,
    extract_model_from_body
)
from tmaps.model import decode_pk
from tmaps.extensions import db
from tmaps.extensions import gc3pie
from tmaps.api import api
from tmaps.error import (
    MalformedRequestError,
    MissingGETParameterError,
    MissingPOSTParameterError,
    ResourceNotFoundError,
    NotAuthorizedError
)

logger = logging.getLogger(__name__)


@api.route('/channel_layers/<channel_layer_id>/tiles', methods=['GET'])
@extract_model_from_path(ChannelLayer)
def get_image_tile(channel_layer):
    """Send a tile image for a specific layer.
    This route is accessed by openlayers."""
    x = request.args.get('x')
    y = request.args.get('y')
    z = request.args.get('z')
    if not x or not y or not z:
        raise MalformedRequestError()
    else:
        x = int(x)
        y = int(y)
        z = int(z)

    tile_file = db.session.query(PyramidTileFile).filter_by(
        column=x, row=y, level=z, channel_layer_id=channel_layer.id
    ).one()
    return send_file(tile_file.location)

@api.route('/features', methods=['GET'])
@jwt_required()
@extract_model_from_path(Experiment, check_ownership=True)
def get_features(experiment):
    """
    Send a list of feature objects.

    Request
    -------

    Required GET parameters:
        - experiment_id

    Response
    --------

    {
        "data": {
            mapobject_type_name: [
                {
                    "name": string
                },
                ...
            ],
            ...
        }
    }

    """
    experiment_id = request.args.get('experiment_id')
    if not experiment_id:
        raise MalformedRequestError(
            'The GET parameter "experiment_id" is required.')

    features = db.session.query(Feature).filter_by(experiment_id=experiment_id).all()

    return jsonify({
        'data': features
    })


@api.route('/experiments', methods=['GET'])
@jwt_required()
def get_experiments():
    """
    Get all experiments for the current user.

    Response
    --------
    {
        "data": list of experiment objects,
    }

    """
    return jsonify({
        'data': current_identity.experiments
    })


@api.route('/experiments/<experiment_id>', methods=['GET'])
@jwt_required()
@extract_model_from_path(Experiment)
def get_experiment(experiment):
    """
    Get an experiment by id.

    Response
    --------
    {
        "data": an experiment object serialized to json
    }

    """
    return jsonify({
        'data': experiment
    })


@api.route('/experiments/<experiment_id>/workflow/submit', methods=['POST'])
@jwt_required()
@extract_model_from_path(Experiment)
def submit_workflow(experiment):
    logger.info('submit workflow')
    data = json.loads(request.data)
    data = data['description']
    WorkflowType = tmlib.workflow.registry.get_workflow_description(data['type'])
    workflow_description = WorkflowType(stages=data['stages'])
    workflow_manager = WorkflowManager(experiment.id, 1)
    submission_manager = SubmissionManager(experiment.id, 'workflow')
    submission_id, user_name = submission_manager.register_submission()
    workflow = workflow_manager.create_workflow(
        submission_id, user_name, workflow_description
    )
    gc3pie.store_jobs(experiment, workflow)
    gc3pie.submit_jobs(workflow)

    return jsonify({
        'message': 'ok',
        'submission_id': workflow.submission_id
    })


@api.route('/experiments/<experiment_id>/workflow/resubmit', methods=['POST'])
@jwt_required()
@extract_model_from_path(Experiment)
def resubmit_workflow(experiment):
    logger.info('resubmit workflow')
    data = json.loads(request.data)
    index = data.get('index', 0)
    data = data['description']
    workflow = gc3pie.retrieve_jobs(experiment, 'workflow')
    # TODO: update stage with modified description
    workflow.update_stage(index)
    gc3pie.resubmit_jobs(workflow, index)

    return jsonify({
        'message': 'ok',
        'submission_id': workflow.submission_id
    })


@api.route('/experiments/<experiment_id>/workflow/status', methods=['POST']) 
@jwt_required()
@extract_model_from_path(Experiment)
def get_workflow_status(experiment):
    logger.info('get workflow status')
    workflow = gc3pie.retrieve_jobs(experiment, 'workflow')
    status = gc3pie.get_status_of_submitted_jobs(workflow)
    return jsonify({
        'data': status
    })

@api.route('/experiments', methods=['POST'])
@jwt_required()
def create_experiment():
    data = json.loads(request.data)

    name = data.get('name')
    description = data.get('description', '')
    microscope_type = data.get('microscope_type')
    plate_format = data.get('plate_format')
    plate_acquisition_mode = data.get('plate_acquisition_mode')

    if any([var is None for var in [name, microscope_type, plate_format,
                                    plate_acquisition_mode]]):
        raise MalformedRequestError()

    e = Experiment(
        name=name,
        description=description,
        user_id=current_identity.id,
        microscope_type=microscope_type,
        plate_format=plate_format,
        root_directory=current_app.config['TMAPS_STORAGE'],
        plate_acquisition_mode=plate_acquisition_mode
    )
    db.session.add(e)
    db.session.commit()

    return jsonify({
        'data': e
    })


@api.route('/experiments/<experiment_id>', methods=['DELETE'])
@jwt_required()
@extract_model_from_path(Experiment, check_ownership=True)
def delete_experiment(experiment):
    """Delete an experiment for the current user.

    Response
    --------
    {
        "message": 'Deletion ok'
    }

    """
    db.session.delete(experiment)
    db.session.commit()

    return jsonify(message='Deletion ok')


@api.route('/plates/<plate_id>', methods=['GET'])
@jwt_required()
@extract_model_from_path(Plate, check_ownership=True)
def get_plate(plate):
    return jsonify(data=plate)


@api.route('/plates', methods=['GET'])
@jwt_required()
def get_plates():
    """
    Get all plates for a specific experiment.

    Request
    -------

    Required GET parameters:
        - experiment_id

    Response
    --------

    {
        "data": [
            {
                "id": string,
                "name": string,
                "description": string,
                "experiment_id": number,
                "acquisition": Object
            },
            ...
        ]
    }

    """
    experiment_id = request.args.get('experiment_id')
    if not experiment_id:
        raise MissingGETParameterError('experiment_id')
    experiment = db.session.query(Experiment).get_with_hash(experiment_id)
    if not experiment:
        raise ResourceNotFoundError('Experiment')
    if not experiment.belongs_to(current_identity):
        raise NotAuthorizedError()

    return jsonify(data=experiment.plates)


@api.route('/plates/<plate_id>', methods=['DELETE'])
@jwt_required()
@extract_model_from_path(Plate, check_ownership=True)
def delete_plate(plate):
    db.session.delete(plate)
    db.session.commit()

    return jsonify(message='Deletion ok')


@api.route('/plates', methods=['POST'])
@jwt_required()
@extract_model_from_body(Experiment, check_ownership=True)
def create_plate(experiment):
    """
    Create a new plate for the experiment with id `experiment_id`.

    Request
    -------

    {
        name: string,
        description: string,
        experiment_id: string
    }

    Response
    --------

    Plate object

    """
    data = json.loads(request.data)
    name = data.get('name')
    desc = data.get('description', '')

    if not name:
        raise MissingPOSTParameterError('name')

    pl = Plate(
        name=name, description=desc,
        experiment_id=experiment.id
    )
    db.session.add(pl)
    db.session.commit()

    return jsonify(data=pl)


@api.route('/acquisitions', methods=['POST'])
@jwt_required()
@extract_model_from_body(Plate, check_ownership=True)
def create_acquisition(plate):
    """
    Create a new acquisition for the plate with id `plate_id`.

    Request
    {
        name: string,
        description: string,
        plate_id: string
    }

    Response
    --------

    Acquisition object

    """
    data = json.loads(request.data)
    name = data.get('name')
    desc = data.get('description', '')

    if not name:
        raise MissingPOSTParameterError('name')

    aq = Acquisition(
        name=name, description=desc,
        plate_id=plate.id
    )
    db.session.add(aq)
    db.session.commit()

    return jsonify(data=aq)


@api.route('/acquisitions/<acquisition_id>', methods=['DELETE'])
@jwt_required()
@extract_model_from_path(Acquisition, check_ownership=True)
def delete_acquisition(acquisition):
    db.session.delete(acquisition)
    db.session.commit()
    return jsonify(message='Deletion ok')


@api.route('/acquisitions/<acquisition_id>', methods=['GET'])
@jwt_required()
@extract_model_from_path(Acquisition, check_ownership=True)
def get_acquisition(acquisition):
    return jsonify(data=acquisition)


@api.route('/acquisitions/<acquisition_id>/image_files', methods=['GET'])
@jwt_required()
@extract_model_from_path(Acquisition, check_ownership=True)
def get_acquisition_image_files(acquisition):
    return jsonify(
        data=[{'name': f.name} for f in acquisition.microscope_image_files]
    )


@api.route('/acquisitions/<acquisition_id>/metadata_files', methods=['GET'])
@jwt_required()
@extract_model_from_path(Acquisition, check_ownership=True)
def get_acquisition_metadata_files(acquisition):
    return jsonify(
        data=[{'name': f.name} for f in acquisition.microscope_metadata_files]
    )
