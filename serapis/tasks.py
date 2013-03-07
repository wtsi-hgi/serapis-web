from celery import Task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
import pysam
import os
import requests
import errno

import simplejson       
import time
import hashlib
#import MySQLdb
from MySQLdb import connect, cursors
from MySQLdb import Error as mysqlError
from MySQLdb import OperationalError

#import serializers
from serapis.constants import *
from _abcoll import Iterable
import collections





BASE_URL = "http://localhost:8000/api-rest/submissions/"

USER_ID = 'user_id'
SUBMISSION_ID = 'submission_id'
TASK_RESULT = 'task_result'
TASK_NAME = 'task_name'
FILE_PATH = 'file_path'
FILE_ID = 'file_id'
PERMISSION_DENIED = "PERMISSION_DENIED"

STUDY_LIST = 'study_list'
LIBRARY_LIST = 'library_list'
SAMPLE_LIST = 'sample_list'
INDIVIDUALS_LIST = 'individuals_list'


FILE_ERROR_LOG = 'file_error_log'
FILE_UPLOAD_STATUS = "file_upload_status"   #("SUCCESS", "FAILURE")
FILE_SEQSCAPE_MDATA_STATUS = 'file_seqsc_mdata_status'
MD5 = "md5"

logger = get_task_logger(__name__)

#---------- Auxiliary functions - used by all tasks ------------

def serialize(data):
    return simplejson.dumps(data)


def deserialize(data):
    return simplejson.loads(data)

#
#def deserialize(data):
#    return json.loads(data)

def build_url(submission_id, file_id):
    #url_str = [BASE_URL, "user_id=", user_id, "/submission_id=", str(submission_id), "/file_id=", str(file_id),"/"]
    url_str = [BASE_URL,  "submission_id=", str(submission_id), "/file_id=", str(file_id),"/"]
    url_str = ''.join(url_str)
    return url_str



####### CLASS THAT ONLY DEALS WITH SEQSCAPE DB ######
class QuerySeqScape():
    
    def connect(self, host, port, user, db):
        try:
            conn = connect(host=host,
                                 port=port,
                                 user=user,
                                 db=db,
                                 cursorclass=cursors.DictCursor
                                 )
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
            raise
        except OperationalError as e:
            print "OPERATIONAL ERROR: ", e.message
            raise
        return conn

    

    def get_sample_data(self, connection, sample_field_name, sample_field_val):
        '''This method queries SeqScape for a given sample_name.'''
        data = None     # result to be returned
        try:
            cursor = connection.cursor()
            query = "select internal_id, name, accession_number, sanger_sample_id, public_name, reference_genome, organism, cohort, gender, ethnicity, geographical_region, common_name  from current_samples where "
            query = query + sample_field_name + "='" + sample_field_val + "' and is_current=1;"
            cursor.execute(query)
            data = cursor.fetchall()
            print "DATABASE SAMPLES FOUND: ", data
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
        return data
    
    
    
    # TODO: Modify fct so that it gets as parameter multiple query criteria
    # TODO: deal differently with diff exceptions thrown here, + try reconnect if connection fails
    def get_library_data(self, connection, library_field_name, library_field_val):
        data = None
        try:
            cursor = connection.cursor()
            query = "select internal_id, name, library_type, public_name from current_library_tubes where " + library_field_name + "='" + library_field_val + "' and is_current=1;"
            cursor.execute(query)
            data = cursor.fetchall()
            print "DATABASEL Libraries FOUND: ", data
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])  #args[0] = error code, args[1] = error text
        return data
    
    

    def get_study_data(self, connection, study_field_name, study_field_val):
        try:
            cursor = connection.cursor()
            query = "select internal_id, accession_number, name, study_type, study_title, faculty_sponsor, ena_project_id, reference_genome from current_studies where "
            query = query + study_field_name + "=" + study_field_val + "and is_current=1;"
            cursor.execute(query)
            data = cursor.fetchall()
            print "DATABASE STUDY FOUND: ", data    
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
        return data

    
    

#############################################################################
#--------------------- PROCESSING SEQSCAPE DATA ---------
############ DEALING WITH SEQSCAPE DATA - AUXILIARY FCT  ####################
class QueryAndProcessSeqScapeData():
    
    def __init__(self):
        self.seqscape_cls = QuerySeqScape()
        self.connection = self.seqscape_cls.connect(SEQSC_HOST, SEQSC_PORT, SEQSC_USER, SEQSC_DB_NAME)  # CONNECT TO SEQSCAPE
        
    
    #"select internal_id, library_type, public_name from current_library_tubes where name=%s and is_current=1;", library_name)
    def lib_seqsc2my_dbmodel(self, lib_mdata):
        ''' Translating the field names from SeqScape model into my own DB model.'''
        result_dict = dict()
        for key, val in lib_mdata.items():
            if key == 'public_name':
                result_dict[LIBRARY_PUBLIC_NAME] = val
            elif key == 'name':
                result_dict[LIBRARY_NAME]= val
            elif key == 'library_type':
                result_dict[LIBRARY_TYPE] = val
        return result_dict
       
       

#"select internal_id, accession_number, sanger_sample_id, public_name, reference_genome, organism, cohort, gender, ethnicity, geographical_region, common_name  from current_samples where name=%s and is_current=1;", sample_name)
    def sampl_seqsc2my_dbmodel(self, sampl_mdata):
        result_dict = dict()
        for key, val in sampl_mdata.items():
            if key == 'internal_id':
                pass
            elif key == 'accession_number':
                result_dict[SAMPLE_ACCESSION_NR] = val
            elif key == 'name':
                result_dict[SAMPLE_NAME] = val
            elif key == 'public_name':
                result_dict[SAMPLE_PUBLIC_NAME] = val
            elif key == 'cohort':
                result_dict[INDIVIDUAL_COHORT] = val
            elif key == 'gender':
                result_dict[INDIVIDUAL_SEX] = val
            elif key == 'ethnicity':
                result_dict[INDIVIDUAL_ETHNICITY] = val
            else:
                result_dict[key] = val
        return result_dict
        
        

    def study_seqsc2my_model(self, study_mdata):
        result_dict = dict()
        for key, val in study_mdata.items():
            if key == 'internal_id':
                pass
            elif key == 'name':
                result_dict[STUDY_NAME] = val
            elif key == 'accession_number':
                result_dict[STUDY_ACCESSION_NR]= val
            elif key == 'faculty_sponsor':
                result_dict[STUDY_FACULTY_SPONSOR]
            elif key == 'reference_genome':
                result_dict[STUDY_REFERENCE_GENOME] = val
            else:
                result_dict[key] = val
        return result_dict
       

    
    #############################################################
    
    def updata_study_mdata(self, old_study_mdata_list, new_study_mdata_list):
        ''' Updates the mdata for each study in the old list with the info in new study list. 
        Adds the unexisting entries. '''
        updated_study_list = []
        for study_new in new_study_mdata_list:
            was_found = False
            for study_old in old_study_mdata_list:
                if study_new[STUDY_NAME] == study_old[STUDY_NAME]:  # existing library - we update it:
                    if not study_old.has_key(STUDY_TYPE) and study_new.has_key(STUDY_TYPE):
                        study_old[STUDY_TYPE] = study_new[STUDY_TYPE]
                    if not study_old.has_key(STUDY_ACCESSION_NR) and study_new.has_key(STUDY_ACCESSION_NR):
                        study_old[STUDY_ACCESSION_NR] = study_new[STUDY_ACCESSION_NR]
                    if not study_old.has_key(STUDY_FACULTY_SPONSOR) and study_new.has_key(STUDY_FACULTY_SPONSOR):
                        study_old[STUDY_FACULTY_SPONSOR] = study_new[STUDY_FACULTY_SPONSOR]
                    if not study_old.has_key(STUDY_REFERENCE_GENOME) and study_new.has_key(STUDY_REFERENCE_GENOME):
                        study_old[STUDY_REFERENCE_GENOME] = study_new[STUDY_REFERENCE_GENOME]
                    if not study_old.has_key(STUDY_TITLE) and study_new.has_key(STUDY_TITLE):
                        study_old[STUDY_TITLE] = study_new[STUDY_TITLE]
                    if not study_old.has_key(STUDY_TYPE) and study_old.has_key(STUDY_TYPE):
                        study_old[STUDY_TYPE] = study_new[STUDY_TYPE]
                    updated_study_list.append(study_old)     
                    was_found = True
                    break
            if was_found == False:
                updated_study_list.append(study_new)
        return updated_study_list

    
    def update_lib_mdata(self, old_lib_mdata_list, new_lib_mdata_list):
        ''' Update the lib list in file mdata with the new mdata extracted from SeqScape for each lib.
            The new mdata replaces the old one, if any existing. '''
        updated_lib_list = []
        for lib_new in new_lib_mdata_list:
            was_found = False
            for lib_old in old_lib_mdata_list:
                if lib_new[LIBRARY_NAME] == lib_old[LIBRARY_NAME]:  # existing library - we update it:
                    if not lib_old.has_key(LIBRARY_TYPE) and lib_new.has_key(LIBRARY_TYPE):
                        lib_old[LIBRARY_TYPE] = lib_new[LIBRARY_TYPE]
                    if not lib_old.has_key(LIBRARY_PUBLIC_NAME) and lib_new.has_key(LIBRARY_PUBLIC_NAME):
                        lib_old[LIBRARY_PUBLIC_NAME] = lib_new[LIBRARY_PUBLIC_NAME]
                    updated_lib_list.append(lib_old)     
                    was_found = True
                    break
            if was_found == False:
                updated_lib_list.append(lib_new)
        return updated_lib_list



    def update_sampl_mdata(self, old_sampl_mdata_list, new_sampl_mdata_list):
        ''' Updates the existing (old) samples' list with the findings from the new_sampl_mdata_list '''
        updated_sampl_list = []
        for sampl_new in new_sampl_mdata_list:
            was_found = False
            for sampl_old in old_sampl_mdata_list:
                if sampl_new[SAMPLE_NAME] == sampl_old[SAMPLE_NAME] or sampl_new[SAMPLE_ACCESSION_NR] == sampl_old[SAMPLE_ACCESSION_NR]:    # I update the old info about my sample:
                    if not sampl_old.has_key(SAMPLE_NAME) and sampl_new.has_key(SAMPLE_NAME):
                        sampl_old[SAMPLE_NAME] = sampl_new[SAMPLE_NAME]
                    if not sampl_old.has_key(SAMPLE_ACCESSION_NR) and sampl_new.has_key(SAMPLE_ACCESSION_NR):
                        sampl_old[SAMPLE_ACCESSION_NR] = sampl_new[SAMPLE_ACCESSION_NR]
                    if not sampl_old.has_key(SANGER_SAMPLE_ID) and sampl_new.has_key(SANGER_SAMPLE_ID):
                        sampl_old[SANGER_SAMPLE_ID] = sampl_new[SANGER_SAMPLE_ID]
                    if not sampl_old.has_key(SAMPLE_PUBLIC_NAME) and sampl_new.has_key(SAMPLE_PUBLIC_NAME):
                        sampl_old[SAMPLE_PUBLIC_NAME] = sampl_new[SAMPLE_PUBLIC_NAME]
                    if not sampl_old.has_key(REFERENCE_GENOME) and sampl_new.has_key(REFERENCE_GENOME):
                        sampl_old[REFERENCE_GENOME] = sampl_new[REFERENCE_GENOME]
                    if not sampl_old.has_key(TAXON_ID) and sampl_new.has_key(TAXON_ID):
                        sampl_old[TAXON_ID] = sampl_new[TAXON_ID]
                    if not sampl_old.has_key(INDIVIDUAL_SEX) and sampl_new.has_key(INDIVIDUAL_SEX):
                        sampl_old[INDIVIDUAL_SEX] = sampl_new[INDIVIDUAL_SEX]
                    if not sampl_old.has_key(INDIVIDUAL_COHORT) and sampl_new.has_key(INDIVIDUAL_COHORT):
                        sampl_old[INDIVIDUAL_COHORT] = sampl_new[INDIVIDUAL_COHORT]
                    if not sampl_old.has_key(INDIVIDUAL_ETHNICITY) and sampl_new.has_key(INDIVIDUAL_ETHNICITY):
                        sampl_old[INDIVIDUAL_ETHNICITY] = sampl_new[INDIVIDUAL_ETHNICITY]
                    if not sampl_old.has_key(GEOGRAPHICAL_REGION) and sampl_new.has_key(GEOGRAPHICAL_REGION):
                        sampl_old[GEOGRAPHICAL_REGION] = sampl_new[GEOGRAPHICAL_REGION]
                    if not sampl_old.has_key(COUNTRY_OF_ORIGIN) and sampl_new.has_key(COUNTRY_OF_ORIGIN):
                        sampl_old[COUNTRY_OF_ORIGIN] = sampl_new[COUNTRY_OF_ORIGIN]
                    if not sampl_old.has_key(ORGANISM) and sampl_new.has_key(ORGANISM):
                        sampl_old[ORGANISM] = sampl_new[ORGANISM]
                    if not sampl_old.has_key(COMMON_NAME) and sampl_new.has_key(COMMON_NAME):
                        sampl_old[COMMON_NAME] = sampl_new[COMMON_NAME]
                    updated_sampl_list.append(sampl_old)
                    was_found = True
                    break
            if was_found == False:
                updated_sampl_list.append(sampl_new)
        return updated_sampl_list
        

    ################ AUXILLIARY FCT: ###############           
                
    def filter_nulls(self, data_dict):
        '''Given a dictionary, it removes the entries that have values = None '''
        for key, val in data_dict.items():
            if val is None or val is " ":
                data_dict.pop(key)
        return data_dict            
    
    
    ################## FILLING IN THE ERROR LISTS - MISSING ENTITIES OR NOT UNIQUELY IDENTIF in SEQSCAPE ######

    def update_missing_entities_errorlist(self, missing_entities, updated_entities, search_field):
        missing_entities_new_list = []
        for missing_ent in missing_entities:
            was_updated = False
            for upd_ent in updated_entities:
                if upd_ent[search_field] == missing_ent[search_field]:
                    was_updated = True
                    break
            if was_updated == False:
                missing_entities_new_list.append({search_field : missing_ent})
        return missing_entities_new_list
    
    
    def update_too_many_rows_errorlist(self, too_many_errorlist, updated_entities, search_field):
        too_many_entities_new_list = []
        for ent in too_many_errorlist:
            was_updated = False
            for upd_ent in updated_entities:
                if upd_ent[LIBRARY_NAME] == ent[search_field]:
                    was_updated = True
                    break
            if was_updated == False:
                too_many_entities_new_list.append({search_field : ent})
        return too_many_entities_new_list
    
    
    def update_file_mdata_missing_entities(self, file_mdata, updated_entities, ents_not_found_seqsc, entity_name, search_field):
        if file_mdata.has_key(ERROR_RESOURCE_MISSING):
            missing_ents_dict = file_mdata[ERROR_RESOURCE_MISSING]
            if missing_ents_dict.has_key(entity_name):
                missing_ents_list = missing_ents_dict[entity_name]
            else:
                missing_ents_list = []
                missing_ents_dict[entity_name] = missing_ents_list
        else:
            file_mdata[ERROR_RESOURCE_MISSING] = dict()
            missing_ents_list = []
            file_mdata[ERROR_RESOURCE_MISSING][entity_name] = missing_ents_list
            
        missing_ents_list = self.update_missing_entities_errorlist(missing_ents_list, updated_entities, search_field)
        missing_ents_list.extend(ents_not_found_seqsc)
        file_mdata[ERROR_RESOURCE_MISSING][entity_name] = missing_ents_list     
        print "MISSING RESOURCES: ", missing_ents_list
        print "FILE MDATA ERROR RESOURCE MISSING: ", file_mdata[ERROR_RESOURCE_MISSING]
        return file_mdata
    
    
    def update_file_mdata_not_unique_entities(self, file_mdata, updated_entities, too_many_dbrows_list, entity_name, search_field):
        if file_mdata.has_key(ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE):
            too_many_ents_dict = file_mdata[ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE]
            if too_many_ents_dict.has_key(entity_name):
                too_many_ents_list = too_many_ents_dict[entity_name]
            else:
                too_many_ents_list = []
                too_many_ents_dict[entity_name] = too_many_ents_list
        else:
            file_mdata[ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE] = dict()
            too_many_ents_list = []
            file_mdata[ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE][entity_name] = too_many_ents_list
            
        too_many_ents_list = self.update_too_many_rows_errorlist(too_many_ents_list, updated_entities, search_field)
        too_many_ents_list.extend(too_many_dbrows_list)
        file_mdata[ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE][entity_name] = too_many_ents_list    # ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE={'library': [{'name': 'bcX98J21 1'}]}
        print "TOO MANY LIBS LIST: ", too_many_ents_list 
        print "FILE MDATA ERROR RESOURCE NOT UNIQUE: ", file_mdata[ERROR_RESOURCE_NOT_UNIQUE_SEQSCAPE]
        return file_mdata
        
    # Query SeqScape for all the library names found in BAM header
    def libs_mdata_lookup(self, incomplete_libs_list, file_mdata):
        search_field = 'name'
        entity_name = 'library'
        libs_not_found_seqsc = []
        too_many_libs_found = []
        result_lib_list = []
        updated_libs = []   
        for lib_name in incomplete_libs_list:
            lib_mdata = self.seqscape_cls.get_library_data(self.connection, search_field, lib_name)    # {'library_type': None, 'public_name': None, 'barcode': '26', 'uuid': '\xa62\xe', 'internal_id': 50087L}
            print "LIB DATA FROM SEQSCAPE:------- ",lib_mdata 
            if len(lib_mdata) == 0:
                result_lib_list.append({"library_name" : lib_name})
                libs_not_found_seqsc.append({search_field : lib_name})
            elif len(lib_mdata) > 1:
                too_many_libs_found.append({search_field : lib_name})
                print "LIB IS ITERABLE....LENGTH: ", len(lib_mdata), " this is the TOO MANY LIST: ", too_many_libs_found
            elif len(lib_mdata) == 1:
                lib_mdata = lib_mdata[0]                        # get_lib_data returns a tuple in which each element is a row in seqscDB
                lib_mdata = self.lib_seqsc2my_dbmodel(lib_mdata)
                lib_mdata = self.filter_nulls(lib_mdata)
                result_lib_list.append(lib_mdata)
                updated_libs.append(lib_mdata)
        print "LIBRARY LIST: ", result_lib_list
        
        # UPDATE EXISTING MDATA FOR EACH LIST:
        file_mdata[LIBRARY_LIST] = self.update_lib_mdata(file_mdata[LIBRARY_LIST], result_lib_list)

        # UPDATE MISSING LIBS LIST:
        if len(libs_not_found_seqsc) > 0:
            file_mdata = self.update_file_mdata_missing_entities(file_mdata, updated_libs, libs_not_found_seqsc, entity_name, search_field)
        else:
            print "NO MISSING LIBS!"

        # UPDATE THE LIBS NOT_UNIQUE_SEQSCAPE:
        if len(too_many_libs_found) > 0: 
            self.update_file_mdata_not_unique_entities(file_mdata, updated_libs, too_many_libs_found, entity_name, search_field)            
        else:
            print "NO TOO MANY ROWS ERRORS - LIBS!!"    
                
                
    ########## SAMPLE LOOKUP ############
    # Look up in SeqScape all the sample names in header that didn't have a complete mdata in my DB. 
    def sampl_mdata_lookup(self, incomplete_sampl_list, file_mdata):
        entity_name = 'sample'
        sampl_not_found_seqsc = []
        too_many_sampl_found = []
        result_sampl_list = []
        updated_samples = []
        for sampl_name in incomplete_sampl_list:
            search_field = 'name'
            sampl_data = self.seqscape_cls.get_sample_data(self.connection, search_field, sampl_name)    # {'library_type': None, 'public_name': None, 'barcode': '26', 'uuid': '\xa62\xe', 'internal_id': 50087L}
            if len(sampl_data) == 0:
                search_field = 'accession_number'
                sampl_data = self.seqscape_cls.get_sample_data(self.connection, search_field, sampl_name) 
            print "SAMPLE DATA FROM SEQSCAPE:------- ",sampl_data
            if len(sampl_data) == 0:
                result_sampl_list.append({search_field : sampl_name})
                sampl_not_found_seqsc.append({search_field : sampl_name})
            elif len(sampl_data) > 1:
                print "SAMPLE IS ITERABLE....LENGTH: ", len(sampl_data)
                too_many_sampl_found.append({search_field : sampl_name})
            elif len(sampl_data) == 1:
                sampl_data = sampl_data[0]  # get_sampl_data - returns a tuple having each row as an element of the tuple ({'cohort': 'FR07', 'name': 'SC_SISuCVD5295404', 'internal_id': 1359036L,...})
                sampl_data = self.sampl_seqsc2my_dbmodel(sampl_data)
                sampl_data = self.filter_nulls(sampl_data)
                result_sampl_list.append(sampl_data)
        print "SAMPLE_LIST: ", result_sampl_list
                
        search_field = 'name'
        # UPDATE EXISTING MDATA FOR EACH LIST:
        file_mdata[SAMPLE_LIST] = self.update_sampl_mdata(file_mdata[SAMPLE_LIST], result_sampl_list)
            
        # UPDATE MISSING SAMPLES LIST:
        if len(sampl_not_found_seqsc) > 0:
            file_mdata = self.update_file_mdata_missing_entities(file_mdata, updated_samples, sampl_not_found_seqsc, entity_name, search_field)
        else:
            print "NO MISSING SAMPLES!"
     
        # UPDATE THE LIBS NOT_UNIQUE_SEQSCAPE:
        if len(too_many_sampl_found) > 0: 
            self.update_file_mdata_not_unique_entities(file_mdata, updated_samples, too_many_sampl_found, entity_name, search_field)            
        else:
            print "NO TOO MANY ROWS ERRORS - LIBS!!"    
     
     
    def study_mdata_lookup(self, incomplete_study_list, file_mdata):
        pass
    
     
############################################
# --------------------- TASKS --------------
############################################

class UploadFileTask(Task):
    ignore_result = True


    def change_state_event(self, state):
        connection = self.app.broker_connection()
        evd = self.app.events.Dispatcher(connection=connection)
        try:
            self.update_state(state="CUSTOM")
            evd.send("task-custom", state="CUSTOM", result="THIS IS MY RESULT...", mytag="MY TAG")
        finally:
            evd.close()
            connection.close()

    
    def md5_and_copy(self, source_file, dest_file):
        src_fd = open(source_file, 'rb')
        dest_fd = open(dest_file, 'wb')
        m = hashlib.md5()
        while True:
            data = src_fd.read(128)
            if not data:
                break
            dest_fd.write(data)
            m.update(data)
        src_fd.close()
        dest_fd.close()
        return m.hexdigest()

    
    def calculate_md5(self, file_path):
        file_obj = file(file_path)
        md5 = hashlib.md5()
        while True:
            data = file_obj.read(128)
            if not data:
                break
            md5.update(data)
        return md5.hexdigest()
    
    
    # file_id, file_submitted.file_path_client, submission_id, user_id
    def run(self, **kwargs):
        time.sleep(2)
        
        file_id = kwargs['file_id']
        file_path = kwargs['file_path']
        submission_id = str(kwargs['submission_id'])
        #user_id = kwargs['user_id']
        src_file_path = file_path
        
        #RESULT TO BE RETURNED:
        #result = init_result(user_id, file_id, file_path, submission_id)
        result = dict()
        dest_file_dir = "/home/ic4/tmp/serapis_staging_area/"
        (src_dir, src_file_name) = os.path.split(src_file_path)
        dest_file_path = os.path.join(dest_file_dir, src_file_name)
        try:
            # CALCULATE MD5 and COPY FILE:
            md5_src = self.md5_and_copy(src_file_path, dest_file_path)
            
            # CALCULATE MD5 FOR DEST FILE, after copying:
            md5_dest = self.calculate_md5(dest_file_path)
            try:
                if md5_src == md5_dest:
                    print "MD5 are EQUAL! CONGRAAAATS!!!"
                    result[MD5] = md5_src
                else:
                    print "MD5 DIFFERENT!!!!!!!!!!!!!!"
                    raise UploadFileTask.retry(self, args=[file_id, file_path, submission_id], countdown=1, max_retries=2 ) # this line throws an exception when max_retries is exceeded
            except MaxRetriesExceededError:
                print "EXCEPTION MAX "
                #result[FILE_UPLOAD_STATUS] = "FAILURE"
                result[FILE_ERROR_LOG] = "ERROR COPYING - DIFFERENT MD5. NR OF RETRIES EXCEEDED."
                raise
        
        except IOError as e:
            if e.errno == errno.EACCES:
                print "PERMISSION DENIED!"
                result[FILE_ERROR_LOG] = "ERROR COPYING - PERMISSION DENIED."
        
                ##### TODO ####
                # If permission denied...then we have to put a new UPLOAD task in the queue with a special label,
                # to be executed on user's node...  
                # result[FAILURE_CAUSE : PERMISSION_DENIED]
            else:
                print "OTHER IO ERROR FOUND: ", e.errno
                result[FILE_ERROR_LOG] = "ERROR COPYING FILE - IO ERROR: "+e.errno
            raise

        return result



    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        file_id = kwargs['file_id']
        submission_id = str(kwargs['submission_id'])
        #user_id = kwargs['user_id']
                
        print "UPLOAD FILES AFTER_RETURN STATUS: ", status
        print "RETVAL: ", retval, "TYPE -------------------", type(retval)

        result = dict()        
        if status == "RETRY":
            return
        elif status == "FAILURE":
            result[FILE_UPLOAD_STATUS] = "FAILURE"
            if isinstance(retval, MaxRetriesExceededError):
                result[FILE_ERROR_LOG] = "ERROR IN UPLOAD - DIFFERENT MD5. NR OF RETRIES EXCEEDED."
            elif isinstance(retval, IOError):
                result[FILE_ERROR_LOG] = "IO ERROR"
        elif status == "SUCCESS":
            result = retval
            result[FILE_UPLOAD_STATUS] = "SUCCESS"
        else:
            print "DIFFERENT STATUS THAN THE ONES KNOWN: ", status
            return
            
        url_str = build_url(submission_id, file_id)
        response = requests.put(url_str, data=serialize(result), headers={'Content-Type' : 'application/json'})
        print "SENT PUT REQUEST. RESPONSE RECEIVED: ", response
        
#        if response.status_code is not 200:
#            UploadFileTask.retry()



class ParseBAMHeaderTask(Task):
    HEADER_TAGS = {'CN', 'LB', 'SM', 'DT'}  # PU, PL, DS?
    ignore_result = True
   
    # TODO: PARSE PU - if needed

    ######### HEADER PARSING #####
    def get_header_mdata(self, file_path):
        ''' Parse BAM file header using pysam and extract the desired fields (HEADER_TAGS)
            Returns a list of dicts, like: [{'LB': 'bcX98J21 1', 'CN': 'SC', 'PU': '071108_IL11_0099_2', 'SM': 'bcX98J21 1', 'DT': '2007-11-08T00:00:00+0000'}]'''
        bamfile = pysam.Samfile(file_path, "rb" )
        header = bamfile.header['RG']
    
        for header_grp in header:
            for header_elem_key in header_grp.keys():
                if header_elem_key not in self.HEADER_TAGS:
                    header_grp.pop(header_elem_key) 
        print "HEADER -----------------", header
        return header
    
    
    def process_json_header(self, header_json):
        ''' Gets the header and extracts from it a list of libraries, a list of samples, etc. '''
        from collections import defaultdict
        dictionary = defaultdict(set)
        for map_json in header_json:
            for k,v in map_json.items():
                dictionary[k].add(v)
        back_to_list = {}
        for k,v in dictionary.items():
            #back_to_list = {k:list(v) for k,v in dictionary.items()}
            back_to_list[k] = list(v)
        return back_to_list
    
    
    ######### ENTITIES IN HEADER LOOKUP #######
    
    #Looks up library names to check if they are complete in mdata.
    def process_header_lib_list(self, header_library_list, file_library_list):
        ''' Compares the information about each library in the header with the information existing already in the DB
            about that library. If the lib is complete, nothing happens. If the info about a lib is incomplete in the DB
            than it adds it to a list of incomplete libraries. '''
        incomplete_libs = []
        for lib_name_h in header_library_list:
            found = False
            for lib in file_library_list:
                if lib['library_name'] == lib_name_h:
                    if lib['library_type'] == None or lib['library_public_name'] == None:
                        incomplete_libs.append(lib_name_h)
                    found = True
                    break
            if found == False:
                incomplete_libs.append(lib_name_h)
        return incomplete_libs
        
    
    def process_header_sampl_list(self, header_samples_list, file_samples_list):
        incomplete_samples = []
        for sample_name_h in header_samples_list:
            found = False
            for sampl in file_samples_list:
                if sampl['sample_name'] == sample_name_h or sampl['sanger_sample_id'] == sample_name_h:
                    if sampl['sample_tissue_type'] == None or sampl['sample_public_name'] == None:
                        incomplete_samples.append(sample_name_h)
                    found = True
                    break
            if found == False:
                incomplete_samples.append(sample_name_h)
        return incomplete_samples
    
    
 
    
    ###############################################################
    
    def run(self, **kwargs):
#        user_id = kwargs['user_id']
#        file_path = kwargs['file_path']
#        file_id = kwargs['file_id']
        #submission_id = kwargs['submission_id']
        file_serialized = kwargs['file_mdata']
        file_mdata = deserialize(file_serialized)
        
        #result = init_result(user_id, file_id, file_path, submission_id)
 
        try:
            header_json = self.get_header_mdata(file_mdata['file_path_client'])  # header =  [{'LB': 'bcX98J21 1', 'CN': 'SC', 'PU': '071108_IL11_0099_2', 'SM': 'bcX98J21 1', 'DT': '2007-11-08T00:00:00+0000'}]
            header_processed = self.process_json_header(header_json)    #  {'LB': ['lib_1', 'lib_2'], 'CN': ['SC'], 'SM': ['HG00242']} 
            
            header_library_list = header_processed['LB']
            header_sample_list = header_processed['SM']
            #header_seq_centers = header_processed['CN']
            
            
            ########## COMPARE FINDINGS WITH EXISTING MDATA ##########
            incomplete_libs_list = self.process_header_lib_list(header_library_list, file_mdata['library_list'])  # List of incomplete libs
            incomplete_sampl_list = self.process_header_sampl_list(header_sample_list, file_mdata['sample_list'])
            
            processSeqsc = QueryAndProcessSeqScapeData()
            processSeqsc.libs_mdata_lookup(incomplete_libs_list, file_mdata)
            processSeqsc.sampl_mdata_lookup(incomplete_sampl_list, file_mdata)

            print "LIBRARY UPDATED LIST: ", file_mdata[LIBRARY_LIST]
            print "SAMPLE_UPDATED LIST: ", file_mdata[SAMPLE_LIST]
        except ValueError:
            raise             
                        
                        
                        


#            
#            result[TASK_RESULT] = header_processed    # options: INVALID HEADER or the actual header
#            print "RESULT FROM BAM HEADER: ", result
#        except ValueError:
#            result[FILE_ERROR_LOG] = "ERROR PARSING BAM FILE. HEADER INVALID. IS THIS BAM FILE?"
#            result['file_header_mdata_status'] = "FAILURE"
#            url_str = build_url(user_id, submission_id, file_id)
#            response = requests.put(url_str, data=serialize(result), headers={'Content-Type' : 'application/json'})
#            print "SENT PUT REQUEST. RESPONSE RECEIVED: ", response
#            raise
#        return result




#    def after_return(self, status, retval, task_id, args, kwargs, einfo):
#        if status == "FAILURE":
#            print "BAM FILE HEADER PARSING FAILED - THIS IS RETVAL: ", retval
#            url_str = [BASE_URL, "user_id=", kwargs['user_id'], "/submission_id=", str(kwargs['submission_id']), "/file_id=", str(kwargs['file_id']),"/"]
#            url_str = ''.join(url_str)
#            response = requests.put(url_str, data=serialize(retval), headers={'Content-Type' : 'application/json'})
#            print "SENT PUT REQUEST. RESPONSE RECEIVED: ", response

# TODO: to modify so that parseBAM sends also a PUT message back to server, saying which library ids he found
# then the DB will be completed with everything we can get from seqscape. If there will be libraries not found in seqscape,
# these will appear in MongoDB as Library objects that only have library_name initialized => NEED code that iterates over all
# libs and decides whether it is complete or not



class QuerySeqScapeForSampleTask(Task):
    ignore_result = True
    
    def connect(self, host, port, user, db):
        try:
            conn = connect(host=host,
                                 port=port,
                                 user=user,
                                 db=db,
                                 cursorclass=cursors.DictCursor
                                 )
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
            raise
        except OperationalError as e:
            print "OPERATIONAL ERROR: ", e.message
            raise
        return conn
    
    
class QuerySeqScapeForLibrariesTask(Task):
    '''Takes a list of libraries and returns a list of metadata for each library as a structures. '''
    def run(self, **kwargs):    
        pass
    
    


class QuerySeqScapeTask(Task):
    ignore_result = True
    
    def connect(self, host, port, user, db):
        try:
            conn = connect(host=host,
                                 port=port,
                                 user=user,
                                 db=db,
                                 cursorclass=cursors.DictCursor
                                 )
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
            raise
        except OperationalError as e:
            print "OPERATIONAL ERROR: ", e.message
            raise
        return conn
    
    
    def filter_nulls(self, data_dict):
        '''Given a dictionary, it removes the entries that have values = None '''
        for key, val in data_dict.items():
            if val is None or val is " ":
                data_dict.pop(key)
        return data_dict

    
    def split_sample_indiv_data(self, sample_dict):
        '''Extracts in a different dict the data regarding the individual to whom the sample belongs.'''
        indiv_data_dict = dict({'cohort' : sample_dict['cohort'], 
                           'gender' : sample_dict['gender'], 
                           'ethnicity' : sample_dict['ethnicity'], 
                           'organism' : sample_dict['organism'],
                           'common_name' : sample_dict['common_name'],
                           'geographical_region' : sample_dict['geographical_region']
                           })
        sample_data_dict = dict({#'uuid' : sample_dict['uuid'],
                                 'internal_id' : sample_dict['internal_id'],
                                 'reference_genome' : sample_dict['reference_genome']
                                 })
        return dict({'sample' : sample_data_dict, 'individual': indiv_data_dict})


    def get_sample(self, connection, sample_name):
        '''This method queries SeqScape for a given sample_name.'''
        try:
            cursor = connection.cursor()
            # uuid, 
            cursor.execute("select internal_id, reference_genome, organism, cohort, gender, ethnicity, geographical_region, common_name  from current_samples where name=%s;", sample_name)
            data = cursor.fetchone()
            if data is None:    # SM may be sample_name or accession_number in SEQSC
                cursor.execute("select internal_id, reference_genome, organism, cohort, gender, ethnicity, geographical_region, common_name  from current_samples where accession_number=%s;", sample_name)
                data = cursor.fetchone()    # uuid 
                print "DB result: reference:", data['reference_genome'], "ethnicity ", data['ethnicity']
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
        return data
    
    
    def get_library(self, connection, library_name):
        try:
            cursor = connection.cursor()
            cursor.execute("select internal_id, library_type, public_name, barcode from current_library_tubes where name=%s;", library_name)
            data = cursor.fetchone()
            if data is not None:
                print "DB result - internal id:", data['internal_id'], "type ", data['library_type'], " public name: ", data['public_name']
                data = self.filter_nulls(data)
            else:
                print "LIBRARY NOT FOUND IN SEQSCAPE!!!!!"
                
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
        return data


    
    def run(self, args_dict):
        print "THIS IS WHAT SEQSC TAASSKK RECEIVED: ", args_dict
#        user_id = args_dict[USER_ID]
#        submission_id = args_dict[SUBMISSION_ID]
#        file_id = args_dict[FILE_ID]
        file_header = args_dict[TASK_RESULT]
        # this looks like this: 
        # [{'DT': ['2007-11-08T00:00:00+0000'], 'LB': ['bcX98J21 1'], 'CN': ['SC'], 'SM': ['bcX98J21 1'], 'PU': ['071108_IL11_0099_2']}]
        # LB = library_name
        # CN = center
        # SM = sample_name
        
        # So the info from header looks like:
        #  {'LB': ['lib_1', 'lib_2'], 'CN': ['SC'], 'SM': ['HG00242']} => iterate over  each list
        
        result = dict()
        library_list = file_header['LB']
        seq_center_name_list = file_header['CN']
        sample_name_list = file_header['SM']

        is_complete = True
        result_library_list = []   
        connection = self.connect(constants.SEQSC_HOST, constants.SEQSC_PORT, constants.SEQSC_USER, constants.SEQSC_DB_NAME)
        for lib_name in library_list:
            lib_data = self.get_library(connection, lib_name)    # {'library_type': None, 'public_name': None, 'barcode': '26', 'uuid': '\xa62\xe', 'internal_id': 50087L}
            if lib_data is None:
                is_complete = False
                result_library_list.append({"library_name" : lib_name})
            else:
                result_library_list.append(lib_data)
        
        result_sample_list = []
        result_individual_list = []
        for sample_name in sample_name_list:
            sample_data = self.get_sample(connection, sample_name)
            if sample_data is None:
                is_complete = False
            else:
                split_data = self.split_sample_indiv_data(sample_data)  # split the sample data in individual and sample related data
                indiv_data = split_data['individual']
                sample_data = split_data['sample']
                # FILTER NONEs:
                indiv_data = self.filter_nulls(indiv_data)
                sample_data = self.filter_nulls(sample_data)
                # APPEND to RESULT LISTS:
                result_sample_list.append(sample_data)
                result_individual_list.append(indiv_data)
        # QUERY SEQSCAPE ONLY IF CN = 'SC'
        
        print "LIBRARY LIST: ", result_library_list
        print "SAMPLE_LIST: ", result_sample_list
        print "INDIVIDUAL LIST", result_individual_list
        print "IS COMPLETE: ", is_complete
        
        
        
        result[LIBRARY_LIST] = result_library_list
        result[SAMPLE_LIST] = result_sample_list
        result[INDIVIDUALS_LIST] = result_individual_list
        
        # TODO: THINK about the statuses...which ones remain, which ones go...
        if is_complete:
            result['file_seqsc_mdata_status'] = "COMPLETE"
        else:
            result['file_seqsc_mdata_status'] = "INCOMPLETE" 
        #result['query_status'] = "COMPLETE"   # INCOMPLETE or...("COMPLETE", "INCOMPLETE", "IN_PROGRESS", TOTALLY_MISSING")
        
        time.sleep(2)
        
        print "SEQ SCAPE RESULT BEFORE SENDING IT: ", result
        return result

        ### THis looks like:
#        SEQ SCAPE RESULT BEFORE SENDING IT:
#[2013-02-22 16:45:42,895: WARNING/PoolWorker-2] {'library_list': [], 'submission_id': '"\\"5127a0b4d836192a2f955625\\""', 'task_name': 'serapis.tasks.QuerySeqScapeTask', 'individuals_list': [{'common_name': 'Homo sapiens', 'organism': 'Human'}], 'study_list': [{'study_name': '123'}], 'sample_list': [{'uuid': '\x0f]\xe5\xfe\xb9\xc3\x11\xdf\x9ef\x00\x14O\x01\xa4\x14', 'internal_id': 9476L}], 'file_id': 1, 'task_result': 'TOKEN PASSED from SEQ scape.', 'query_status': 'COMPLETE'}




    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        args = args[0]  # args is a tuple containing a dictionary with the arguments of the run fct
        #if status == "SUCCESS":
        print "ARGS in AFTER RETURN for SEQSCAPE.................", args
        submission_id = str(args['submission_id'])
        print "SEQSCAPE AFTER_RETURN STATUS: ", status
        print "SEQSCAPE RESULT TO BE SENT AWAY: ", retval
        
        result = dict()        
        if status == "RETRY":
            return
        elif status == "FAILURE":
            if isinstance(retval, OperationalError):
                result[FILE_ERROR_LOG] = "SEQSCAPE - CAN'T CONNECT TO MYSQL SERVER "
            result[FILE_SEQSCAPE_MDATA_STATUS] = "FAILURE"
        elif status == "SUCCESS":
            result = retval
            result[FILE_SEQSCAPE_MDATA_STATUS] = "SUCCESS"
        else:
            print "DIFFERENT STATUS THAN THE ONES KNOWN: ", status
            return
        
        print "MESSAGE TO SEND FROM SEQSCAPE TASK BACK ON FAILURE: ", result
        url_str = build_url(args['user_id'], submission_id, str(args['file_id']))
        response = requests.put(url_str, data=serialize(result), headers={'Content-Type' : 'application/json'})
        print "SENT PUT REQUEST. RESPONSE RECEIVED: ", response
        #elif status == "FAILURE":
        
        
        
class QuerySeqscapeForStudyTask(Task):
    def get_study(self, connection, study_field, study_value):
        ''' Query SequenceScape for the study which has study_field=study_value '''
        try:
            cursor = connection.cursor()
            query = "select uuid, study_name, study_type, study_title, study_faculty, study_ena_project_id, reference_genome from current_studies where"
            query = query + study_field + "=" + study_value + ";"
            cursor.execute(query)
            data = cursor.fetchone()
            if data is not None:
                print "DB result - internal id:", data['internal_id'], "type ", data['library_type'], " public name: ", data['public_name']
                data = self.filter_nulls(data)
            else:
                print "LIBRARY NOT FOUND IN SEQSCAPE!!!!!"
                
        except mysqlError as e:
            print "DB ERROR: %d: %s " % (e.args[0], e.args[1])
        return data

    
    def run(self, **kwargs):
        # kwargs: file_id, study_field_name, submission_id, study_field_value
        file_id = kwargs['file_id']
        study_field_name = kwargs['study_field_name']
        study_field_val = kwargs['study_field_value'] 
        submission_id = kwargs['submission_d']
        
        connection = self.connect(constants.SEQSC_HOST, constants.SEQSC_PORT, constants.SEQSC_USER, constants.SEQSC_DB_NAME)
        study = self.get_study(connection, study_field_name, study_field_val)
        
        
        

# --------------------------- NOT USED ------------------------



        #event = Event("my-custom-event")
        #app = self._get_app()
#        print "HERE IT CHANGES THE STATE...."
#        self.update_state(state="CUSTOMized")
#        print "APP NAME -----------------------", self.app.events, " ---- ", self.app.backend
        #connection = current_app.broker_connection()
#        evd = app.events.Dispatcher()
#        try:
#            self.update_state(state="CUSTOM")
#            evd.send("task-custom", state="CUSTOM")
#        finally:
#            evd.close()
#            #connection.close()
        

def query_seqscape2():
    import httplib

    conn = httplib.HTTPConnection(host='localhost', port=20002)
    conn.connect()
    conn.putrequest('GET', 'http://wapiti.com/0_0/requests')
    headers = {}
    headers['Content-Type'] = 'application/json'
    headers['Accept'] = 'application/json'
    headers['Cookie'] = 'WTSISignOn=UmFuZG9tSVbAPOvZGIyv5Y2AcLw%2FKOLddyjrEOW8%2BeE%2BcKuElNGe6Q%3D%3D'
    for k in headers:
        conn.putheader(k, headers[k])
    conn.endheaders()
    
    conn.send(' { "project" : { id : 384 }, "request_type" : { "single_ended_sequencing": { "read_length": 108 } } } ')
    
    resp = conn.getresponse()
    print resp
#    print resp.status
#    print resp.reason
#    print resp.read()
    
    conn.close()
    
#query_seqscape()








#@task()
#def query_seqscape_prohibited():
#    db = MySQLdb.connect(host="mcs12.internal.sanger.ac.uk",
#                         port=3379,
#                         user="warehouse_ro",
#                         passwd="",
#                         db="sequencescape_warehouse"
#                         )
#    cur = db.cursor()
#    cur.execute("SELECT * FROM current_studies where internal_id=2120;")
#
#    for row in  cur.fetchall():
#        print row[0]

#






#import sys, glob
#sys.path.append('/home/ic4/Work/Projects/Serapis-web/Celery_Django_Prj/serapis/test-thrift-4')
#sys.path.append('/home/ic4/Work/Projects/Serapis-web/Celery_Django_Prj/serapis/test-thrift-4/gen-py')
#
#print sys.path
#
#from tutorial.Calculator import *
#from tutorial.ttypes import *
#
#from thrift import Thrift
#from thrift.transport import TSocket
#from thrift.transport import TTransport
#from thrift.protocol import TBinaryProtocol
#
#
#
#@task()
#def call_thrift_task():
#    
#    try:
#        
#    
#        # Make socket
#        transport = TSocket.TSocket('localhost', 9090)
#    
#        # Buffering is critical. Raw sockets are very slow
#        transport = TTransport.TBufferedTransport(transport)
#    
#        # Wrap in a protocol
#        protocol = TBinaryProtocol.TBinaryProtocol(transport)
#    
#        # Create a client to use the protocol encoder
#        client = Client(protocol)
#    
#        # Connect!
#        transport.open()
#    
#        client.ping()
#        print 'ping()'
#    
#        summ = client.add(1,1)
#        print '1+1=%d' % summ
#    
#        work = Work()
#    
#        work.op = Operation.DIVIDE
#        work.num1 = 1
#        work.num2 = 0
#    
#        try:
#            quotient = client.calculate(1, work)
#            print 'Whoa? You know how to divide by zero?'
#        except InvalidOperation, io:
#            print 'InvalidOperation: %r' % io
#    
#        work.op = Operation.SUBTRACT
#        work.num1 = 15
#        work.num2 = 10
#    
#        diff = client.calculate(1, work)
#        print '15-10=%d' % diff
#    
#        log = client.getStruct(1)
#        print 'Check log: %s' % (log.value)
#    
#        # Close!
#        transport.close()
#    
#        return diff
#    except Thrift.TException, tx:
#        print '%s' % (tx.message)
#      
#      
