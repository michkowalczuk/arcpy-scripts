import arcpy
import os
import utils

def merge_shp_by_folders(folder_in, spatial_ref_out, workspace_out):

    arcpy.env.overwriteOutput = True

    workspace_is_folder = utils.is_workspace_folder(workspace_out)

    arcpy.AddMessage("Collecting shapefiles...")
    
    files_to_merge = {}
    for root, _, files in os.walk(folder_in):
        for file in files:
            if(file.lower().endswith(".shp")):
                woj = file[:2]
                pow = file[2:4]
                if woj not in files_to_merge:
                    files_to_merge[woj] = {}

                if pow not in files_to_merge[woj]:
                    files_to_merge[woj][pow] = []
                
                files_to_merge[woj][pow].append(os.path.join(root, file))

    for dataset in files_to_merge.keys():

        dataset_name = dataset if workspace_is_folder else f"woj_{dataset}"

        dataset_path = f"{workspace_out}\\{dataset_name}"
        arcpy.AddMessage(f"Create '{dataset_path}' dataset...")

        utils.create_folder_or_dataset(workspace_out, dataset_name, spatial_ref_out)

        # arcpy.CreateFeatureDataset_management(workspace_out, dataset_name, spatial_ref_out)

        for fc in files_to_merge[dataset].keys():

            if workspace_is_folder:
                fc_out = f"{dataset_path}\\{dataset}{fc}.shp"
            else:
               fc_out = f"{dataset_path}\\pow_{dataset}{fc}"

            if arcpy.Exists(fc_out):
                arcpy.AddMessage(f"{fc_out} exist.")
                continue
            
            arcpy.AddMessage(f"Merging shapefiles to {fc_out}...")
            arcpy.Merge_management(files_to_merge[dataset][fc], fc_out, "", "")
    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    development = (arcpy.GetArgumentCount() == 0) and (arcpy.GetParameter(0) is None)
    
    if development:
        folder_in = r"<folder with BDOT subfolders>"
        spatial_ref_out = arcpy.SpatialReference(2180)
        workspace_out = r"output workspace"
    else:
        folder_in = arcpy.GetParameterAsText(0)
        spatial_ref_out = arcpy.GetParameter(1)
        workspace_out = arcpy.GetParameterAsText(2)
    
    merge_shp_by_folders(folder_in, spatial_ref_out, workspace_out)