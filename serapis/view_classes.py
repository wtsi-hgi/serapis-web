from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect

from serapis.forms import UploadForm
from serapis import controller
from serapis import models
from serapis import exceptions
from serapis import serializers

#from django.http import HttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
#from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from serapis.models import Submission
from serializers import ObjectIdEncoder

from os import listdir
from os.path import isfile, join
from bson.objectid import ObjectId
from pymongo.errors import InvalidId

import errno
import json
import logging
logging.basicConfig(level=logging.DEBUG)
#from serapis.controller import get_submission
        
        
        
#    subm_id_obj = ObjectId(submission_id)
#    submission_qset = models.Submission.objects(_id=subm_id_obj)
#    #submission_qset = models.Submission.objects(__raw__={'_id' : ObjectId(submission_id)})
#    
#    submission = submission_qset.get()   

        

# ----------------------- GET MORE SUBMISSIONS OR CREATE A NEW ONE-------

# /submissions/
class SubmissionsMainPageRequestHandler(APIView):
    # GET all the submissions for a user_id
    def get(self, request, format=None):
        ''' Retrieves all the submissions for this user. '''
        user_id = "ic4"
        submissions_list = controller.get_all_submissions(user_id)
        subm_serialized = serializers.serialize(submissions_list)
        return Response("Submission list: "+subm_serialized, status=200)
    
    
    # POST = create a new submission, for uploading the list of files given as param
    def post(self, request, format=None):
        ''' Creates a new submission, given a set of files.
            No submission is created if the list of files is empty.
            Returns:
                - status=201 if the submission is created
                - status=400 if the submission wasn't created (list of files empty).
        '''
        user_id = "ic4"
        try:
            data = request.POST['_content']
            data_deserial = json.loads(data)
        except ValueError:
            return Response("Not JSON format.", status=400)
        else:
            files_list = data_deserial["files"]
            result_dict = controller.create_submission(user_id, files_list)
            submission_id = result_dict['submission_id']
            if submission_id == None:
                # TODO: what status should be returned when the format of the req is ok, but the data is bad (logically)?
                msg = "Files don't exist. Submission not created."
                result_dict['message'] = msg
                return Response(result_dict, status=400)
            else:
                msg = "Submission created"    
                result_dict['message'] = msg
                return Response(result_dict, status=201)
                
#            perm_denied_list = []
#            other_io_errs = []
#            for err in error_list:
#                if err.errno == errno.EACCES:
#                    perm_denied_list.append(err.filename)
#                else:
#                    other_io_errs.append({"file":err.filename, "error" : err.strerror})
#            if len(perm_denied_list) > 0:
#                err_msg = "PERMISSION DENIED for these files:" + str(perm_denied_list)
#                err_msg = err_msg+". PLEASE RUN THE SCRIPT x ON THE CLUSTER OR GIVE PERMISSION TO USER MERCURY TO READ YOUR FILES! Submission id: "+str(submission_id) 
#                err_msg = err_msg + ". Submission created: " + str(submission_id)
#                return Response(err_msg, status=202)
#            elif len(other_io_errs) > 0:
#                err_msg = "IO Errors in the following files:" + str(other_io_errs)
#                err_msg = err_msg + ". Submission created: " + str(submission_id)
#                return Response(err_msg, status=202)
#            else:
#                return Response("Created the submission with id="+str(submission_id), status=201)


#---------- OLD VERSION:----------
#        except IOError as e:
#            if e.errno == errno.ENOENT:
#                print "NO SUCH FILE"
#                return Response("No such file!!!", status=422) # Unprocessable Entity - here TODO: think about the functionality - subm created or NOT?
#                # or 424: Method Failure
#            else:
#                print "ERROR: ", e
#                return Response(status=424)
#           
        
        
    
# ---------------------- HANDLE 1 SUBMISSION -------------

# /submissions/submission_id
class SubmissionRequestHandler(APIView):
    def get(self, request, submission_id, format=None):
        ''' Retrieves a submission given by submission_id.'''
        try:
            logging.debug("Received GET request - submission id:"+submission_id)
            submission = controller.get_submission(submission_id)
        except InvalidId:
            return Response(status=404)
        else:
            subm_serialized = serializers.serialize(submission)
            return Response("Submission: "+subm_serialized)
        
        
    def put(self, request, submission_id, format=None):
        ''' Updates a submission with the data provided on the POST request.'''
        data = request.DATA
        try:
            controller.update_submission(submission_id, data)
        except InvalidId:
            return Response("No submission with this id!", status=404)
        except exceptions.JSONError as e:
            return Response("Bad request. "+e.message+e.args,status=400)
        except exceptions.ResourceDoesNotExistError as e:
            return Response("File does not exist!", status=404)
        else:
            return Response(status=200)



    def delete(self, request, submission_id):
        ''' Deletes the submission given by submission_id. '''
        try:
            was_deleted = controller.delete_submission(submission_id)
        except InvalidId:
            return Response("No submission with this id!", status=404)
        except exceptions.ResourceDoesNotExistError:
            return Response("No file with this id!", status=404)
        except:
            return Response("OTHER EXCEPTION", status=400)
        else:
            if was_deleted == True:
                return Response(status=200)
            #TODO: here there MUST be treated also the other exceptions => nothing will happen if the app throws other type of exception,
            # it will just prin OTHER EXCEPTIOn - on that branch
        


# /submissions/submission_id/status/
class SubmissionStatusRequestHandler(APIView):
    def get(self, request, submission_id, format=None):
        ''' Retrieves the status of the submission together
            with the statuses of the files (upload and mdata). '''
        submission = controller.get_submission(submission_id)
        if submission != None:
            subm_status = submission.get_status()
            return Response(subm_status, status=200)
        else:
            return Response(status=404)



               

#---------------- HANDLE 1 SUBMITTED FILE ------------------------

class SubmittedFileMainPageRequestHandler(APIView):
    ''' Handles the requests coming for /submissions/123/files/.
        GET is used for retrieving the list of files for this submission.
        POST is used for adding a new file to this submission.'''
    def get(self, request, submission_id, format=None):
        pass
    
    # TODO: should I really expose this method?
    def post(self, request, submission_id, format=None):
        pass
    
    
    
class SubmittedFileRequestHandler(APIView):
    ''' Handles the requests for a specific file (existing already).
        GET - retrieves all the information for this file (metadata)
        POST - resubmits the jobs for this file
        PUT - updates a specific part of the metadata.
        DELETE - deletes this file from this submission.'''
    
    def get(self, request, submission_id, file_id, format=None):
        ''' Retrieves the information regarding this file from this submission.
            Returns 404 if the file or the submission don't exist. '''
        try:
            submission = controller.get_submission(submission_id)
            file_req = submission.get_submitted_file(file_id)
        except:
            return Response("Resource not found or id invalid!", status=404)
        else:
            if file_req != None:
                result = serializers.serialize(file_req)
                logging.debug("RESULT IS: "+result)
                return Response(result, status=200)
            else:
                return Response("Resource not found!", status=404)
            
    def post(self, request, submission_id, file_id, format=None):
        ''' Resubmit jobs for this file - used in case of permission denied.
            The user wants to submit files that mercury does not have permissions on,
            he gets an error message back, and is asked to make a POST req after solving the pb 
            with a parameter indicating how he solved the pb - if he ran himself a worker or just changed file permissions. 
            POST req body should look like: 
            {"permissions_changed : True"} - if he manually changed permissions for this file. '''
        data = request.DATA
        print "POST REQ MADE - DATA: ", data
        #try:
        error_list = controller.resubmit_jobs(submission_id, file_id, data)
        if error_list == None:
            return Response(status=304)
        else:
            result = dict()
            result['errors'] = error_list
            # TODO: How do I know if there were resubmitted or not? it depends on what I have in the errors list...
            # What if there are thrown also other exceptions?
            result['message'] = "Jobs resubmitted."
            return Response(result, status=202)
            
    
    def put(self, request, submission_id, file_id, format=None):
        ''' Updates the corresponding info for this file.'''
        data = request.DATA
        try:
            non_existing_fields = controller.update_file_submitted(submission_id, file_id, data)
            result = dict()
            result['errors'] = "Non-existing fields: "+str(non_existing_fields)
        except exceptions.ResourceDoesNotExistError:
            return Response('Resource does not exist.', status=404)
        else:
            result['message'] = "Successfully updated!"
            return Response(result, status=200)
    
    
    def delete(self, request, submission_id, file_id, format=None):
        ''' Deletes a file. Returns 404 if the file or submission don't exist. '''
        try:
            controller.delete_file_submitted(submission_id, file_id)
        except (InvalidId, exceptions.ResourceDoesNotExistError) as e:
            return Response("Error:"+e.strerror, status=404)
        else:
            return Response("Successfully deleted!", status=200)
        
        
# ------------------- ENTITIES -----------------------------
class LibrariesMainPageRequestHandler(APIView):
    ''' Handles requests /submissions/123/files/3/libraries/.
        GET - retrieves all the libraries that this file contains as metadata.
        POST - adds a new library to the metadata of this file'''
    def get(self,  request, submission_id, file_id, format=None):
        pass
    
    def post(self,  request, submission_id, file_id, library_id, format=None):
        pass
    
    

class LibraryRequestHandler(APIView):
    ''' Handles the requests for a specific library (existing already).
        GET - retrieves the library identified by the id.
        PUT - updates fields of the metadata for the specified library
        DELETE - deletes the specified library from the library list of this file.
    '''
    def get(self, request, submission_id, file_id, library_id, format=None):
        pass

    def put(self, request, submission_id, file_id, library_id, format=None):
        pass
    
    def delete(self, request, submission_id, file_id, library_id, format=None):
        pass
    
    
class SamplesMainPageRequestHandler(APIView):
    ''' Handles requests for /submissions/123/files/12/samples/
        GET - retrieves the list of all samples
        POST - adds a new sample to the list of samples that the file has.
    '''
    def get(self,  request, submission_id, file_id, format=None):
        pass
    
    def post(self,  request, submission_id, file_id, sample_id, format=None):
        pass
    
    
class SampleRequestHandler(APIView):
    ''' Handles requests for a specific sample (existing already).
        GET - retrieves the sample identified by the id.
        PUT - updates fields of the metadata for the specified sample
        DELETE - deletes the specified sample from the sample list of this file.
    '''

    def get(self, request, submission_id, file_id, sample_id, format=None):
        pass

    def put(self, request, submission_id, file_id, sample_id, format=None):
        pass
    
    def delete(self, request, submission_id, file_id, sample_id, format=None):
        pass
    
# ----------
    
class StudyMainPageRequestHandler(APIView):
    ''' Handles requests for /submissions/123/files/12/studies/
        GET - retrieves the list of all studies
        POST - adds a new study to the list of studies that the file has.
    '''
    def get(self,  request, submission_id, file_id, format=None):
        pass
    
    def post(self,  request, submission_id, file_id, study_id, format=None):
        pass
    
    
class StudyRequestHandler(APIView):
    ''' Handles requests for a specific study (existing already).
        GET - retrieves the study identified by the id.
        PUT - updates fields of the metadata for the specified study
        DELETE - deletes the specified study from the study list of this file.
    '''

    def get(self, request, submission_id, file_id, study_id, format=None):
        pass

    def put(self, request, submission_id, file_id, study_id, format=None):
        pass
    
    def delete(self, request, submission_id, file_id, study_id, format=None):
        pass
    
    
# ---------------------------------------------------------


class GetFolderContent(APIView):
    def post(self, request, format=None):
        data = request.DATA
        print "Data received - POST request: ", data
        # CALL getFolder on WORKER...
        return Response({"rasp" : "POST"})
    
         
         

# Get all submissions of this user_id
class GetAllUserSubmissions(APIView):
    def get(self, request, user_id, format=None):
        submission_list = models.Submission.objects.filter(sanger_user_id=user_id)
        return Response(submission_list)


# Get all submissions ever
class GetAllSubmissions(APIView):
    def get(self, request):
        submission_list = models.Submission.objects.all()
        return Response(submission_list)
    
    
# Get all submissions with this status
class GetStatusSubmissions(APIView):
    def get(self, status, request):
        submission_list = models.Submission.objects.filter(submission_status=status)
        return Response(submission_list)
    
    
####---------------------- FOR TESTING PURPOSES -----------
         
        
class MdataInsert(APIView):
    def get(self, request, format=None):
        myObj = {'sampleID' : 1, 'libID' : 2}
        data_serialized = json.dumps(myObj)
        print "SERIALIZED DATA: ", str(data_serialized)
        
        file_list = []
        mypath = "/home/ic4/data-test/bams"
        for f in listdir(mypath):
            if isfile(join(mypath, f)):
                file_list.append(join(mypath, f))
        
        for f in file_list:
            print "File SENT TO WORKER: ", f
            controller.upload_test(f)
            
        return Response(data_serialized)
    
    def post(self, request, format=None):        
        data = JSONParser().parse(request)
        orig = json.loads(data)
        print "ORIGINAL DATA: ", orig
        
        #for i in range(100):
            #controller.upload_test("/home/ic4/data-test/bams/HG00242.chrom11.ILLUMINA.bwa.GBR.exome.20120522.bam")


class MdataUpdate(APIView):
    def get(self, request, format=None):
        print "Update GET Called!"
        data_serialized = json.dumps("Update Get called")
        return Response(data_serialized)
    
    def post(self, request, format=None):
        data = JSONParser().parse(request)
        orig = json.loads(data)
        print "Update POST Called"
        return Response("Update POST called")
        
         
        



#--------------------------------------------------------------------

    
    
    
class UploadView(FormView):
    template_name = "upload.html"
    form_class = UploadForm
    success_url = '/login/'
    def post(self, request, *args, **kwargs):
        form = UploadForm(self.request.POST, self.request.FILES)
        #if form.is_valid():

        files_list = form.handle_multi_uploads(self.request.FILES)
        
#        for f in files_list:
#            data_dict = form.submit_BAM_check(f)
#            
        form.submit_task(files_list)
        
        #print "DATA FROM BAM FILES HEADER: ", data_dict
        return HttpResponseRedirect('/serapis/success/')
        # endif
        #return self.render_to_response(self.get_context_data(form=form))

#    
#    def form_valid(self, form):
#        print 'form valid called'
#        form.submit_task()
#        return super(UploadView, self).form_valid(form)
##    


        # This is how you get timestamp of an obj_creation
        # for obj in submission:
#            id = obj._object_key['pk']
#            print "time stamp: ",  id.generation_time

    