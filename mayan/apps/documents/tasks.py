from __future__ import unicode_literals

import logging

from django.contrib.auth.models import User
from django.core.files import File

from mayan.celery import app

from common.models import SharedUploadedFile

from .models import Document, DocumentPage, DocumentType, DocumentVersion

logger = logging.getLogger(__name__)


@app.task(compression='zlib')
def task_get_document_page_image(document_page_id, *args, **kwargs):
    document_page = DocumentPage.objects.get(pk=document_page_id)
    return document_page.get_image(*args, **kwargs)


@app.task(ignore_result=True)
def task_clear_image_cache():
    logger.info('Starting document cache invalidation')
    # TODO: Notification of success and of errors
    Document.objects.invalidate_cache()
    logger.info('Finished document cache invalidation')


@app.task(ignore_result=True)
def task_update_page_count(version_id):
    document_version = DocumentVersion.objects.get(pk=version_id)
    document_version.update_page_count()


@app.task(ignore_result=True)
def task_new_document(document_type_id, shared_uploaded_file_id, label, description=None, expand=False, language=None, user_id=None):
    shared_uploaded_file = SharedUploadedFile.objects.get(pk=shared_uploaded_file_id)
    document_type = DocumentType.objects.get(pk=document_type_id)

    if user_id:
        user = User.objects.get(pk=user_id)
    else:
        user = None

    with File(file=shared_uploaded_file.file) as file_object:
        Document.objects.new_document(document_type=document_type, expand=expand, file_object=file_object, label=label, description=description, language=language, user=user)

    shared_uploaded_file.delete()

    # TODO: Report/record how was file uploaded
    #    if result['is_compressed'] is None:
    #        messages.success(request, _('File uploaded successfully.'))

    #    if result['is_compressed'] is True:
    #        messages.success(request, _('File uncompressed successfully and uploaded as individual files.'))

    #    if result['is_compressed'] is False:
    #        messages.warning(request, _('File was not a compressed file, uploaded as it was.'))


@app.task(ignore_result=True)
def task_upload_new_version(document_id, shared_uploaded_file_id, user_id, comment=None):
    shared_file = SharedUploadedFile.objects.get(pk=shared_uploaded_file_id)
    document = Document.objects.get(pk=document_id)

    if user_id:
        user = User.objects.get(pk=user_id)
    else:
        user = None

    with File(file=shared_file.file) as file_object:
        try:
            document.new_version(comment=comment, file_object=file_object, user=user)
        except Warning as warning:
            logger.info('Warning during attempt to create new document version for document:%s ; %s', document, warning)
        finally:
            shared_file.delete()
