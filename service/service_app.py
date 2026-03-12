import os
import django
django.setup()

from flask import Flask
from flask_cors import CORS
from flask_restful import Api

from service.controller.ping_controller import Ping
from service.controller.video_controller import VideoDetail, VideoList
from service.controller.upload_controller import UploadConfirm, UploadSignedUrl, UploadUrl
from service.controller.annotation_controller import (
    AnnotationDetail,
    AnnotationList,
    AutoAnnotationInterval,
    AutoAnnotationList,
)

app = Flask(__name__)
CORS(app)
api = Api(app, prefix='/video')

api.add_resource(Ping, '/ping')

api.add_resource(VideoList, '/list')
api.add_resource(VideoDetail, '/<string:video_id>')

api.add_resource(UploadSignedUrl, '/upload/signed-url')
api.add_resource(UploadConfirm, '/upload/confirm')
api.add_resource(UploadUrl, '/upload/url')

api.add_resource(AnnotationList, '/<string:video_id>/annotations')
api.add_resource(AnnotationDetail, '/<string:video_id>/annotations/<string:annotation_id>')
api.add_resource(AutoAnnotationList, '/<string:video_id>/auto-annotations')
api.add_resource(AutoAnnotationInterval, '/<string:video_id>/auto-annotation-interval')

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
