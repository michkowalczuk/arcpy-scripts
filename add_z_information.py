import arcpy

Z_FIELDS = ["Z_Min", "Z_Max"]

def add_z_information(fc):
    fc_fields = [x.baseName for x in arcpy.ListFields(fc)]

    for z_field in Z_FIELDS:
        if not z_field in fc_fields:
            arcpy.AddField_management(fc, z_field, "FLOAT")
            
    with arcpy.da.UpdateCursor(fc, [Z_FIELDS[0], Z_FIELDS[1], Z_FIELDS[2], 'SHAPED@']) as cursor:
        for row in cursor:
            ext = row[3].extent
            row[0] = ext.ZMin
            row[1] = ext.ZMax
            row[2] = ext.ZMax - ext.ZMin

            cursor.updateRow(row)
    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    input_features = arcpy.GetParameterAsText(0)
    if not input_features:
        input_features = r"<your_feature_class>"
    
    add_z_information(input_features)
    
    # Update derived parameter values using arcpy.SetParameter() or arcpy.SetParameterAsText()