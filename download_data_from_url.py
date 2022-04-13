import arcpy
import requests
import os
import pathlib


def download_file(url, dir, prefix):
    path = os.path.join(dir, url.split('/')[-1])
    if os.path.exists(path):
        arcpy.AddWarning("{0}: File already exist: {1}".format(prefix, path))
        return True

    try:
        r = requests.get(url)
        if str(r.status_code) == '404':
            arcpy.AddError("{0}: Url not found: {1}".format(prefix, url))
            return False
        try:
            with open(path, 'wb') as f:
                f.write(r.content)
                arcpy.AddMessage("{0}: {1} saved".format(prefix, path))
            return True
        except IOError:
            arcpy.AddError("{0}: File error: {1}".format(prefix, path))
            return False
        except:
            arcpy.AddError("{0}: Write error: {1}".format(prefix, path))    
    except requests.exceptions.ConnectionError:
        download_file(url, dir, prefix)
        return True
    except:
        arcpy.AddError("{0}: File error: {1}".format(prefix, url))
        return False

def download_data_from_url(in_fc, url_field, out_dir):

    desc = arcpy.Describe(in_fc)
    print("Name: {0}".format(desc.name))
    print("Feature type: {0}".format(desc.featureType))
    print("Shape field name: {0}".format(desc.shapeFieldName))
    print("Shape type: {0}".format(desc.shapeType))
    print("---")

    if(not os.path.exists(out_dir)):
        os.mkdir(out_dir)

    fc_count = int(arcpy.GetCount_management(in_fc)[0])
    arcpy.SetProgressor("step", "Downloading data from url...", 0, fc_count, 1)

    fields = [f.name for f in arcpy.ListFields(in_fc) if f.aliasName == url_field]
    with arcpy.da.SearchCursor(in_fc, fields) as cursor:
        
        for i, row in enumerate(cursor):
            url = row[0]
            arcpy.SetProgressorLabel("Downloading {0}...".format(url))
            prefix_message = "{0} of {1}".format(i+1, fc_count)
            download_file(url, out_dir, prefix_message)
            arcpy.SetProgressorPosition()

    arcpy.ResetProgressor()
    
    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    # Tool parameter accessed with GetParameter or GetParameterAsText
    in_fc = arcpy.GetParameterAsText(0)
    field_url = arcpy.GetParameterAsText(1)
    out_dir = arcpy.GetParameterAsText(2)

    download_data_from_url(in_fc, field_url, out_dir)
