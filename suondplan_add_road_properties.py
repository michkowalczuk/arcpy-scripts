import arcpy

def calculate_new_field(fc, field_name, field_type, expression=""):
    try:
        try:
            arcpy.AddField_management(fc, field_name, field_type)
        except Exception as e:
            arcpy.AddWarning(f"Add field '{field_name}' failed!")
            arcpy.AddWarning(e)

        arcpy.CalculateField_management(fc, field_name, expression, "PYTHON_9.3")
    except Exception as e:
        arcpy.AddWarning(f"Calculate field '{field_name}' failed!")
        arcpy.AddWarning(e)
        
def suondplan_add_road_properties(
    road_in_fc,
    field_name,
    field_section,
    field_id,
    single_band,
    field_width,
    oneway,
    condition_oneway,
    condition_bridge,
    bridge_thickness,
    surface_id,
    road_out_fc
):
    # work in memory
    road_mem_fc = "in_memory\\road"
    arcpy.CopyFeatures_management(road_in_fc, road_mem_fc)
    
    road_lyr = "road_lyr"
    arcpy.MakeFeatureLayer_management(road_mem_fc, road_lyr)
    
    # Main
    if field_name:
        arcpy.AddMessage("Adding 'RdName'...")
        calculate_new_field(road_mem_fc, "RdName", "TEXT", f"!{field_name}!")
    if field_section:
        arcpy.AddMessage("Adding 'RdSection'...")
        calculate_new_field(road_mem_fc, "RdSection", "TEXT",  f"!{field_section}!")
    if field_id:
        arcpy.AddMessage("Adding 'RdID'...")
        calculate_new_field(road_mem_fc, "RdID", "LONG", f"!{field_id}!")

    # Profile
    arcpy.AddMessage("Adding 'SingleBand'...")
    calculate_new_field(road_mem_fc, "SingleBand", "SHORT", single_band)
    if field_width:
        expression = f"!{field_width}!/2"
    else:
        expression = 3.5
    arcpy.AddMessage("Adding 'LeftLane'...")
    calculate_new_field(road_mem_fc, "LeftLane", "DOUBLE", expression)
    arcpy.AddMessage("Adding 'RightLane'...")
    calculate_new_field(road_mem_fc, "RightLane", "DOUBLE", expression)
    arcpy.AddMessage("Adding 'LeftEmis'...")
    calculate_new_field(road_mem_fc, "LeftEmis", "DOUBLE", 0)
    arcpy.AddMessage("Adding 'RightEmis'...")
    calculate_new_field(road_mem_fc, "RightEmis", "DOUBLE", 0)
    arcpy.AddMessage("Adding 'CentralRes'...")
    calculate_new_field(road_mem_fc, "CentralRes", "DOUBLE", 0)

    # Traffic & Speed
    arcpy.AddMessage("Adding 'EntryType'...")
    calculate_new_field(road_mem_fc, "EntryType", "SHORT", 3)
    arcpy.AddMessage("Adding 'OneWay'...")
    calculate_new_field(road_mem_fc, "OneWay", "SHORT", oneway)
    try:
        if condition_oneway:
            arcpy.AddMessage("Assigning 'OneWay'...")
            arcpy.SelectLayerByAttribute_management(
                road_lyr,
                "NEW_SELECTION",
                condition_oneway
            )
            arcpy.CalculateField_management(road_lyr, "OneWay", 1)
            arcpy.SelectLayerByAttribute_management(
                road_lyr,
                "SWITCH_SELECTION",
                ""
            )
            arcpy.CalculateField_management(road_lyr, "OneWay", 0)
    except Exception as e:
        arcpy.AddWarning(f"Cannot meet 'One-way Condition'!")
        arcpy.AddWarning(e)

    # Bridge
    calculate_new_field(road_mem_fc, "Bridge", "DOUBLE", 0)
    try:
        if condition_bridge:
            arcpy.AddMessage("Assigning 'Bridge' properties...")
            arcpy.SelectLayerByAttribute_management(
                road_lyr,
                "NEW_SELECTION",
                condition_bridge
            )
            arcpy.CalculateField_management(road_lyr, "Bridge", 1)
            calculate_new_field(road_lyr, "LeftEdge", "DOUBLE", f"!{field_width}!/2 + 2")
            calculate_new_field(road_lyr, "RightEdge", "DOUBLE", f"!{field_width}!/2 + 2")
            calculate_new_field(road_lyr, "LeftWallH", "DOUBLE", 0)
            calculate_new_field(road_lyr, "RightWallH", "DOUBLE", 0)
            calculate_new_field(road_lyr, "Thickness", "DOUBLE", bridge_thickness)
    except Exception as e:
        arcpy.AddWarning("Cannot meet the 'Bridge Condition'!")
        arcpy.AddWarning(e)    

    # Surface    
    arcpy.AddMessage("Adding 'SurfaceID'...")
    if surface_id:
        expression = f"!{surface_id}!"
    else:
        expression = 17
    calculate_new_field(road_mem_fc, "SurfaceID", "SHORT", expression)

    arcpy.AddMessage("Adding 'AirTemp'...")
    calculate_new_field(road_mem_fc, "AirTemp", "SHORT", 10)

    arcpy.AddMessage(f"Saving {road_out_fc}...")
    arcpy.CopyFeatures_management(road_mem_fc, road_out_fc)
    arcpy.AddMessage("Cleaning...")
    arcpy.Delete_management(road_mem_fc)

    arcpy.AddMessage("Done!")

    return

# This is used to execute code if the file was run but not imported
if __name__ == "__main__":

    # Tool parameter accessed with GetParameter or GetParameterAsText
    road_in_fc = arcpy.GetParameterAsText(0)
    field_name = arcpy.GetParameterAsText(1)
    field_section = arcpy.GetParameterAsText(2)
    field_id = arcpy.GetParameterAsText(3)
    single_band = 1 if arcpy.GetParameter(4) else 0
    field_width = arcpy.GetParameterAsText(5)
    oneway = 1 if arcpy.GetParameter(6) else 0
    condition_oneway = arcpy.GetParameterAsText(7)
    condition_bridge = arcpy.GetParameterAsText(8)
    bridge_thickness = arcpy.GetParameter(9)
    surface_id = arcpy.GetParameter(10)
    road_out_fc = arcpy.GetParameterAsText(11)
    
    suondplan_add_road_properties(
        road_in_fc,
        field_name,
        field_section,
        field_id,
        single_band,
        field_width,
        oneway,
        condition_oneway,
        condition_bridge,
        bridge_thickness,
        surface_id,
        road_out_fc
    )
    