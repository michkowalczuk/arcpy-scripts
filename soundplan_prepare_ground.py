from os import utime
import arcpy
from soundplan_prepare_buildings import FIELD_HOLES
import utils


INTEGRATE_SIZE = 0.1
TEMP_WORKSPACE = "in_memory"
FIELD_PT_XKOD = "X_KOD"
FIELD_AREA = "Area"
FIELD_LENGTH = "Length"

FIELD_PT_TERYT = "TERYT"
FIELD_G = "G"
FIELD_HOLE_ID = "HoleId"
FIELD_HOLE_EDGE_LEN = "HoleEdgeL"
FIELD_HOLE_LEN_ID = "HoleEdgeId"
FIELD_HOLES = "Holes"


FIELD_COUNTY_CODE = "JPT_KOD_JE"
GROUND_ASSIGNMENT = {
    "PTWP01": 0,
    "PTWP02": 0,
    "PTWP03": 0,
    "PTZB01": 0.6,
    "PTZB02": 0.6,
    "PTZB03": 0.2,
    "PTZB04": 0.2,
    "PTZB05": 0.2,
    "PTLZ01": 1,
    "PTLZ02": 1,
    "PTLZ03": 1,
    "PTRK01": 1,
    "PTRK02": 1,
    "PTUT01": 1,
    "PTUT02": 1,
    "PTUT03": 1,
    "PTUT04": 1,
    "PTUT05": 1,
    "PTTR01": 1,
    "PTTR02": 1,
    "PTKM01": 0.3,
    "PTKM02": 0.3,
    "PTKM03": 0.3,
    "PTKM04": 0.3,
    "PTGN01": 0.5,
    "PTGN02": 0.3,
    "PTGN03": 0.3,
    "PTGN04": 0.5,
    "PTPL01": 0.2,
    "PTSO01": 0.5,
    "PTSO02": 0.5,
    "PTWZ01": 0.2,
    "PTWZ02": 0.2,
    "PTNZ01": 0.2,
    "PTNZ02": 0.2
}

def soundplan_prepare_ground(
    workspace_bdot_in, 
    clip_area_in,
    min_hole_area_in,
    ground_out,
    check_output_topology
):
    # in-memory features
    ground_merge_fc = f"{TEMP_WORKSPACE}\\ground_merge"
    ground_merge_clip_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip"
    ground_merge_clip_disG_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip_disG"
    ground_merge_clip_intersectSelf_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip_intersectSelf"
    ground_merge_clip_intersectSelf_disXkod_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip_intersectSelf_disXkod"
    ground_merge_clip_intersectSelf_disXkod_sortArea_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip_intersectSelf_disXkod_sortArea"
    
    ground_merge_clip_errors_fc = f"{TEMP_WORKSPACE}\\ground_merge_clip_errors"
    
    holes_fc = f"{TEMP_WORKSPACE}\\holes"
    holes_single_fc = f"{TEMP_WORKSPACE}\\holes_single"
    holes_single_intersect_ground_fc = f"{TEMP_WORKSPACE}\\holes_single_intersect_ground"
    holes_single_intersect_ground_dis_fc = f"{TEMP_WORKSPACE}\\holes_single_intersect_ground_dis"

    workspace_in_describe = arcpy.Describe(workspace_bdot_in)
    if workspace_in_describe.dataType == 'FeatureDataset':
        # set workspace for the use of the 'ListFeatureClasses' function  
        utils.set_arcpy_environment(workspace_in_describe.path, arcpy.SpatialReference(2180))
        ground_fc_list = arcpy.ListFeatureClasses("*PT*A*", "Polygon", workspace_in_describe.baseName)
    else:
        arcpy.AddError("Not implemented yet")
        return

    if len(ground_fc_list) == 0:
        arcpy.AddError("No PT ground files in the workspace!")
        return
 
    arcpy.AddMessage("Merging ground layers...")
    arcpy.Merge_management(ground_fc_list, ground_merge_fc)

    arcpy.AddMessage("Clipping ground areas...")
    arcpy.PairwiseClip_analysis(ground_merge_fc, clip_area_in, ground_merge_clip_fc)
    arcpy.Delete_management(ground_merge_fc)

    arcpy.AddMessage("Integrating ground areas...")
    arcpy.PairwiseIntegrate_analysis(ground_merge_clip_fc, INTEGRATE_SIZE)

    arcpy.AddMessage("Fixing self intersections...")
    arcpy.PairwiseIntersect_analysis(
        ground_merge_clip_fc,
        ground_merge_clip_intersectSelf_fc
    )
    arcpy.PairwiseDissolve_analysis(
        ground_merge_clip_intersectSelf_fc,
        ground_merge_clip_intersectSelf_disXkod_fc,
        FIELD_PT_XKOD
    )
    arcpy.Delete_management(ground_merge_clip_intersectSelf_fc)

    # Extract only features surrounding error features to speed-up geoprocessing operations
    ground_merge_clip_lyr = utils.create_layer_name(ground_merge_clip_fc)
    arcpy.MakeFeatureLayer_management(ground_merge_clip_fc, ground_merge_clip_lyr)
    arcpy.SelectLayerByLocation_management(
        ground_merge_clip_lyr,
        "INTERSECT",
        ground_merge_clip_intersectSelf_disXkod_fc
    )
    
    # save features with errors to a separate fc
    arcpy.Select_analysis(ground_merge_clip_lyr, ground_merge_clip_errors_fc)
    
    # delete them in original dataset
    arcpy.DeleteFeatures_management(ground_merge_clip_lyr)

    arcpy.CalculateGeometryAttributes_management(
        ground_merge_clip_intersectSelf_disXkod_fc,
        [[FIELD_AREA, "AREA"]]
    )
    arcpy.Sort_management(
        ground_merge_clip_intersectSelf_disXkod_fc,
        ground_merge_clip_intersectSelf_disXkod_sortArea_fc,
        FIELD_AREA
    )
    arcpy.Delete_management(ground_merge_clip_intersectSelf_disXkod_fc)
    
    ground_merge_clip_intersectSelf_disXkod_sortArea_lyr = utils.create_layer_name(ground_merge_clip_intersectSelf_disXkod_sortArea_fc)
    arcpy.MakeFeatureLayer_management(
        ground_merge_clip_intersectSelf_disXkod_sortArea_fc,
        ground_merge_clip_intersectSelf_disXkod_sortArea_lyr
    )
    
    field_object_id = arcpy.Describe(ground_merge_clip_intersectSelf_disXkod_sortArea_fc).OIDFieldName
    ids = utils.list_field_values(ground_merge_clip_intersectSelf_disXkod_sortArea_fc, field_object_id)

    in_fc = ground_merge_clip_errors_fc
    out_fc = ""
    for id in ids:
        select_query = f"{field_object_id} = {id}"
        arcpy.SelectLayerByAttribute_management(
            ground_merge_clip_intersectSelf_disXkod_sortArea_lyr,
            "NEW_SELECTION",
            select_query
        )

        out_fc = f"{ground_merge_clip_errors_fc}_{id}"
        utils.update(
            in_fc,
            ground_merge_clip_intersectSelf_disXkod_sortArea_lyr,
            out_fc
        )
        in_fc = out_fc

    out_fc = out_fc if out_fc else ground_merge_clip_errors_fc
    arcpy.Append_management(out_fc, ground_merge_clip_fc, "NO_TEST")  

    arcpy.AddMessage("Assigning G values...")
    arcpy.AddField_management(ground_merge_clip_fc, FIELD_G, "FLOAT")
    with arcpy.da.UpdateCursor(ground_merge_clip_fc, [FIELD_PT_XKOD, FIELD_G]) as cursor:
        for row in cursor:
            code = row[0]
            if code in GROUND_ASSIGNMENT:
                g = GROUND_ASSIGNMENT[code]
            else:
                arcpy.AddError(f"{code} does not exist in ground assignment dictionary!")
            row[1] = g

            cursor.updateRow(row)

    arcpy.AddMessage("Dissolving polygons...")
    arcpy.PairwiseDissolve_analysis(
        ground_merge_clip_fc,
        ground_merge_clip_disG_fc,
        FIELD_G,
        multi_part="SINGLE_PART" # must be singlepart to use selection by area
    )
    arcpy.CalculateGeometryAttributes_management(
        ground_merge_clip_disG_fc,
        [[FIELD_AREA, "AREA"]]
    )

    arcpy.AddMessage("Deleting small holes...")
    ground_merge_clip_disG_lyr = utils.create_layer_name(ground_merge_clip_disG_fc)
    arcpy.MakeFeatureLayer_management(ground_merge_clip_disG_fc, ground_merge_clip_disG_lyr)
    arcpy.SelectLayerByAttribute_management(
        ground_merge_clip_disG_lyr,
        "NEW_SELECTION",
        f"{FIELD_AREA} < {min_hole_area_in}"
    )
    arcpy.DeleteFeatures_management(ground_merge_clip_disG_lyr)

    arcpy.AddMessage("Filling holes...")
    arcpy.PairwiseErase_analysis(clip_area_in, ground_merge_clip_disG_fc, holes_fc)

    arcpy.MultipartToSinglepart_management(holes_fc, holes_single_fc)

    field_object_id = arcpy.Describe(holes_single_fc).OIDFieldName
    arcpy.CalculateField_management(
        holes_single_fc,
        FIELD_HOLE_ID,
        f"!{field_object_id}!"
    )
    
    arcpy.PairwiseIntersect_analysis(
        [holes_single_fc, ground_merge_clip_disG_fc],
        holes_single_intersect_ground_fc,
        output_type="LINE"
    )

    arcpy.CalculateField_management(
        holes_single_intersect_ground_fc,
        FIELD_HOLE_EDGE_LEN,
        "!Shape.length!*1000",
        "PYTHON3",
        field_type="LONG"
    )

    arcpy.PairwiseDissolve_analysis(
        holes_single_intersect_ground_fc,
        holes_single_intersect_ground_dis_fc,
        FIELD_HOLE_ID,
        [[FIELD_HOLE_EDGE_LEN, "MAX"]],
        "SINGLE_PART"
    )    
    
    # add HoleId prefix to join field to avoid incorrect assignment
    arcpy.CalculateField_management(
        holes_single_intersect_ground_fc,
        FIELD_HOLE_LEN_ID,
        f'str(!{FIELD_HOLE_ID}!) + "_" + str(!{FIELD_HOLE_EDGE_LEN}!)',
        "PYTHON3",
        field_type="TEXT"
    )
    arcpy.CalculateField_management(
        holes_single_intersect_ground_dis_fc,
        FIELD_HOLE_LEN_ID,
        f'str(!{FIELD_HOLE_ID}!) + "_" + str(!MAX_{FIELD_HOLE_EDGE_LEN}!)',
        "PYTHON3",
        field_type="TEXT"
    )

    arcpy.JoinField_management(
        holes_single_intersect_ground_dis_fc,
        FIELD_HOLE_LEN_ID,
        holes_single_intersect_ground_fc,
        FIELD_HOLE_LEN_ID,
        FIELD_G
    )

    arcpy.JoinField_management(
        holes_single_fc,
        FIELD_HOLE_ID,
        holes_single_intersect_ground_dis_fc,
        FIELD_HOLE_ID,
        FIELD_G
    )

    arcpy.Append_management(
        holes_single_fc,
        ground_merge_clip_disG_fc,
        "NO_TEST"
    )

    arcpy.AddMessage(f"Saving ground areas to: {ground_out}...")
    
    arcpy.PairwiseDissolve_analysis(
        ground_merge_clip_disG_fc,
        ground_out,
        FIELD_G,
        multi_part="SINGLE_PART"
    )

    if check_output_topology:
        arcpy.AddMessage("Checking output topology...")
        # Holes test
        ground_out_dis_fc = f"{TEMP_WORKSPACE}\\ground_out_dis"
        arcpy.PairwiseDissolve_analysis(
            ground_out,
            ground_out_dis_fc
        )
        arcpy.CalculateGeometryAttributes_management(
            ground_out_dis_fc,
            [[FIELD_HOLES, "HOLE_COUNT"]] 
        )
        holes_count = sum(utils.list_field_values(ground_out_dis_fc, FIELD_HOLES))
        if holes_count:
            arcpy.AddWarning(f"Output dataset has {holes_count} hole(s).")

        # Self-intersection test
        ground_out_intersectSelf_fc = f"{TEMP_WORKSPACE}\\ground_out_intersectSelf"
        arcpy.PairwiseIntersect_analysis(
            ground_out,
            ground_out_intersectSelf_fc
        )
        intersection_count = int(arcpy.GetCount_management(ground_out_intersectSelf_fc)[0])
        if intersection_count:
            arcpy.AddWarning(f"Output dataset has {intersection_count} self-intersection(s).")

    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    # Tool parameter accessed with GetParameter or GetParameterAsText
    workspace_bdot_in = arcpy.GetParameterAsText(0)
    if not workspace_bdot_in:
        workspace_bdot_in = r"<BDOT folder>"

    clip_area_in = arcpy.GetParameterAsText(1)
    if not clip_area_in:
        clip_area_in = r"<shapefile with area of interest>"

    min_hole_area_in = arcpy.GetParameter(2)
    if not min_hole_area_in:
        min_hole_area_in = 500

    ground_out = arcpy.GetParameterAsText(3)
    if not ground_out:
        ground_out = r"output feature class with ground areas>"

    check_output_topology = arcpy.GetParameter(4)
    if not check_output_topology:
        check_output_topology = True

    soundplan_prepare_ground(
        workspace_bdot_in, 
        clip_area_in,
        min_hole_area_in,
        ground_out,
        check_output_topology
    )