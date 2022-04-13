import arcpy
import os


def set_arcpy_environment(workspace, spatial_ref):
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = workspace
    arcpy.env.cartographicCoordinateSystem = spatial_ref

def is_workspace_folder(workspace):
    workspace_desc = arcpy.Describe(workspace) 
    if workspace_desc.dataType == "Folder":
        return True
    else:
        return False 

def create_folder_or_dataset(workspace, name, cs):
    if is_workspace_folder(workspace):
        folder_name = f"{workspace}\\{name}"
        if(not os.path.exists(folder_name)):
            os.mkdir(folder_name)
    else:
        arcpy.CreateFeatureDataset_management(workspace, name, cs)

def replace_dots_in_paths(folder, symbol="_"):
    for root, _, files in os.walk(folder):
        for file in files:
            [file_name, file_ext] = os.path.splitext(file)
            new_file_name = file_name.replace(".", symbol)

            if file_name.count(".") > 0:
                file_path = os.path.join(root, file)
                new_file = new_file_name + file_ext
                new_file_path = os.path.join(root, new_file)
                
                os.rename(file_path, new_file_path)

def list_field_names(fc):
    return [f.baseName for f in  arcpy.ListFields(fc)]

def create_layer_name(fc):
    return fc.split("\\")[-1] + "_lyr"

def list_field_values(fc, field):
    return [row[0] for row in arcpy.da.SearchCursor(fc, field)]

def update(in_features, update_features, out_feature_class):
    workspace = "in_memory"

    arcpy.AddMessage("Updating features...")
    dis_fc = f"{workspace}\\dis"
    arcpy.PairwiseDissolve_analysis(update_features, dis_fc)
    erase_fc = f"{workspace}\\erase"

    arcpy.PairwiseErase_analysis(in_features, dis_fc, erase_fc)
    arcpy.Merge_management([erase_fc, update_features], out_feature_class)

    arcpy.Delete_management(dis_fc)
    arcpy.Delete_management(erase_fc)
    