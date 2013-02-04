import json

from serapis import tasks
from serapis.models import PilotModel

# Gets the list of uploaded files and moves them in the specified area (path)
# keeps the original file name
def handle_multi_uploads(files):
    files_list = []
    for upfile in files.getlist('file_field'):
        filename = upfile.name
        print "upfile.name = ", upfile.name
        
        path="/home/ic4/tmp/serapis_dest/"+filename
        files_list.append(path)
        fd = open(path, 'w')
        for chunk in upfile.chunks():
            fd.write(chunk)
        fd.close()  
    return files_list


# Gets the list of files, parses header and returns the header info as a DICT
def submit_BAM_check(bamfile):
    print "Hello from submit_BAM check on server! BEFORE task submission..."
    result = (tasks.parse_BAM_header.delay(bamfile)).get()     
    print "Hello from submit_BAM check AFTER TASK SUBMISSION. RESULT: ", result
    return result




def form2json(form, files_list):
    print 'submit task called!!!'
    print 'Fields received: ', form.data['lane_name']
    print form.data['library_name']
    
    pilot_object = PilotModel()
    pilot_object.lane_name = form.data['lane_name']
    pilot_object.sample_name = form.data['sample_name']
    pilot_object.library_name = form.data['library_name']
    pilot_object.individual_name = form.data['individual_name']
    pilot_object.study_name = form.data['study_name']
    pilot_object.file_list = files_list

    
    data_serialized = json.dumps(pilot_object.__dict__["_data"])
    print "SERIALIZED DATA: ", str(data_serialized)


    orig = json.loads(data_serialized)
    print "DESERIALIZED: ", orig
    
    
    
    
def upload_files(request_files, form):
    print "TYpe of request file type: ", type(request_files)
    files_list = handle_multi_uploads(request_files)
        
    for f in files_list:
        data_dict = submit_BAM_check(f)
        print "DATA FROM BAM FILES HEADER: ", data_dict
        
    form2json(form, files_list)
    
    

def upload_test(f):
    data_dict = submit_BAM_check(f)
    print "DATA FROM BAM FILES HEADER: ", data_dict
    return data_dict
    
    
    
