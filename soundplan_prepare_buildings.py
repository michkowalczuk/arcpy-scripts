import arcpy
import utils

TESSELLATION_SIZE_FACTOR = 0.9

FIELD_SHAPE = "Shape"

FIELD_BUBD_LOKALNYID = "LOKALNYID"
FIELD_BUBD_FUNOGBUD = "FUNOGBUD"
FIELD_BUBD_FUNSZCZ = "FUNSZCZ"
FIELD_BUBD_LKOND = "LKOND"
FIELD_BUBD_X_INFDOD = "X_INFDOD"
FIELD_BUBD_X_KOD = "X_KOD"
FIELD_BUBD_OBJECTID = "OBJECTID"
FIELD_BUBD_TERYT = "TERYT"

FIELD_3D_BUILDINGID = "buildingId"
FIELD_3D_AKTZRODLA = "aktZrodla"

FIELD_X = "X"
FIELD_Y = "Y"
FIELD_ZMIN = "Z_Min"
FIELD_ZMAX = "Z_Max"
FIELD_HOLES = "Holes"
    
# Building attributes:
# >> general function from BDOT ('FUNOGBUD')
FIELD_NAME = "Name"

# >> detailed function from BDOT ('FUNSZCZ')
FIELD_SP_DETAILED = "Detail"

# >> BDOT code ('X_KOD')
FIELD_SP_CODE = "Code"

# >> Additional information from BDOT ('X_INFDOD')
FIELD_SP_ADD_INFO = "Add_Info"

# >> ID from BDOT ('LOKALNYID')
FIELD_SP_ROAD_NAME = "Road_Name"

# >> type encoded from BDOT ('X_KOD'):
# -1 - unknown
#  0 - main
#  1 - auxiliary building
# -2 - school
# -3 - hospital
# -4 - kindergarten
FIELD_SP_TYPE = "Build_Type"
BUILDING_TYPE_UNKNOWN = -1
BUILDING_TYPE_MAIN = 0
BUILDING_TYPE_AUX = 1
BUILDING_TYPE_SCHOOL = -2
BUILDING_TYPE_HOSPITAL = -3
BUILDING_TYPE_KINDERGARTEN = -4
BUILDING_TYPES = {
    BUILDING_TYPE_MAIN:
        f"""UPPER({FIELD_BUBD_X_KOD}) = 'BUBD01' 
        OR UPPER({FIELD_BUBD_X_KOD}) = 'BUBD02'
        OR UPPER({FIELD_BUBD_X_KOD}) = 'BUBD03'
        OR UPPER({FIELD_BUBD_X_KOD}) = 'BUBD04'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%karny%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%poprawczy%'""",    
    BUILDING_TYPE_SCHOOL:
        f"""LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%szko_a%'""",
    BUILDING_TYPE_HOSPITAL:
        f"""LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%szpital%' 
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%bezdomnych%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%hospicjum%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%opiekispolecznej%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%sanatorium%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%nieletnich%'""",
    BUILDING_TYPE_KINDERGARTEN:
        f"""LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%przedszkole%'
        OR LOWER({FIELD_BUBD_FUNSZCZ}) LIKE '%zlobek%'"""
}

# >> height
FIELD_SP_HEIGHT = "Height"

# >> height source:
# '3D' - from 3d buildings (LOD1)
# 'BDOT' - from number of floors
# 'NMT' - elevation (Z Min) taken from NMT ASCII GRID
# using SAGA "Grid Statistics for Polygons (Mean), Method: [2] polygon wise (cell area)"
FIELD_SP_HEIGHT_SOURCE = "H_Src"
HEIGHT_SOURCE_3D = "LOD_3D"
HEIGHT_SOURCE_BDOT = "BDOT_LONKD"

FIELD_SP_ELEV_SOURCE = "Z_Min_Src"
ELEV_SOURCE_NMT = "NMT_ASCII"

# >> number of floors ('LKOND')
FIELD_SP_FLOORS = "Floors"

def soundplan_prepare_buildings(
    buildings_bubd,
    buildings_3d,
    buildings_elev,
    field_elev,
    buffer_in,
    buildings_out,
    no_holes
):
    arcpy.env.overwriteOutput = True

    use_3d = True if buildings_3d else False
    use_elev = True if buildings_elev else False
    
    fields_bubd = utils.list_field_names(buildings_bubd)
        
    buildings_bubd_buf_memory = r"in_memory\buildings_bubd_buf"
    buildings_bubd_layer = "buildings_bubd_lyr"
    buildings_bubd_memory_layer = "buildings_bubd_memory_lyr"
    
    # Use SelectByLocation instead of Clip to avoid tiny buildings on the buffer edge,
    # and for a performance reason. 
    if buffer_in:
        arcpy.AddMessage("Collecting data in a buffer...")
        
        buffer_in_memory = r"in_memory\buffer_in"
        arcpy.CopyFeatures_management(buffer_in, buffer_in_memory)
        arcpy.MakeFeatureLayer_management(buildings_bubd, buildings_bubd_layer)
        arcpy.SelectLayerByLocation_management(buildings_bubd_layer, "WITHIN", buffer_in)
    
    arcpy.Select_analysis(buildings_bubd_layer, buildings_bubd_buf_memory)
    
    if use_3d:
        arcpy.AddMessage("Preparing building 3D data...")
        
        buildings_3d_memory = r"in_memory\buildings_3d"
        buildings_3d_buf_memory = r"in_memory\buildings_3d_buf"
        buildings_3d_layer = "buildings_3d_lyr"

        # Create in-memory point representation of 3D buildings
        
        # Prevent long geometry calculations
        fields_3d = utils.list_field_names(buildings_3d)
        if not(FIELD_X in fields_3d and FIELD_Y in fields_3d and FIELD_ZMIN in fields_3d and FIELD_ZMAX in fields_3d):
            arcpy.CalculateGeometryAttributes_management(
                buildings_3d,
                [[FIELD_X, "CENTROID_X"],
                [FIELD_Y, "CENTROID_Y"],
                [FIELD_ZMIN, "EXTENT_MIN_Z"],
                [FIELD_ZMAX, "EXTENT_MAX_Z"]]
            )

        arcpy.XYTableToPoint_management(
            buildings_3d,
            buildings_3d_memory,
            FIELD_X,
            FIELD_Y,
            FIELD_ZMIN,
            arcpy.Describe(buildings_3d).spatialReference
        )

        # do not use Clip on Multipach,
        # otherwise use geo selection 
        arcpy.MakeFeatureLayer_management(buildings_3d_memory, buildings_3d_layer)
        if buffer_in:
            arcpy.SelectLayerByLocation_management(buildings_3d_layer, "INTERSECT", buffer_in)
        
        arcpy.Select_analysis(buildings_3d_layer, buildings_3d_buf_memory)

        arcpy.AddMessage("Adding field indexes...")
        try:
            arcpy.AddIndex_management(
                buildings_bubd_buf_memory,
                FIELD_BUBD_LOKALNYID,
                FIELD_BUBD_LOKALNYID.upper(),
                "UNIQUE",
                "NON_ASCENDING"
            )
        except Exception as e:
            arcpy.AddWarning(f"Can't add index for field '{FIELD_BUBD_LOKALNYID}':")
            arcpy.AddWarning(str(e))

        try:
            arcpy.AddIndex_management(
                buildings_3d_memory,
                FIELD_3D_BUILDINGID,
                FIELD_3D_BUILDINGID.upper(),
                "UNIQUE",
                "NON_ASCENDING"
            )
        except Exception as e:
            arcpy.AddWarning(f"Can't add index for field '{FIELD_3D_BUILDINGID}':")
            arcpy.AddWarning(str(e))

        arcpy.AddMessage("Joining fields...")
        arcpy.JoinField_management(
            buildings_bubd_buf_memory,
            FIELD_BUBD_LOKALNYID,
            buildings_3d_buf_memory,
            FIELD_3D_BUILDINGID,
            f"{FIELD_3D_AKTZRODLA};{FIELD_ZMIN};{FIELD_ZMAX}"
        )
        
        # legacy...
        export_building_centroids_3d = False
        if export_building_centroids_3d:
            building_nmt_path = buildings_out.replace(".shp", "_NMT.shp")
            arcpy.AddMessage(f"Saving DGM 3D points from 3D buildings: {building_nmt_path}...")
            arcpy.Select_analysis(buildings_3d_buf_memory, building_nmt_path)

        arcpy.AddMessage("Freeing resources in memory...")
        arcpy.Delete_management(buildings_3d_memory)
        arcpy.Delete_management(buildings_3d_buf_memory)

    if use_elev:
        arcpy.AddMessage("Preparing building elevation data (NMT ASCII GRID)...")
        buildings_elev_buf_memory = r"in_memory\buildings_elev_buf"
        buildings_elev_layer = "buildings_elev_lyr"

        arcpy.MakeFeatureLayer_management(buildings_elev, buildings_elev_layer)
        if buffer_in:
            arcpy.SelectLayerByLocation_management(buildings_elev_layer, "INTERSECT", buffer_in)
        
        arcpy.Select_analysis(buildings_elev_layer, buildings_elev_buf_memory)

    arcpy.AddMessage("Adding SoundPLAN fields...")
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_NAME, "TEXT", field_length=50)
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_ROAD_NAME, "TEXT", field_length=50)
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_TYPE, "SHORT",)
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_HEIGHT, "FLOAT")
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_FLOORS, "SHORT")
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_HEIGHT_SOURCE, "TEXT", field_length=10)
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_ELEV_SOURCE, "TEXT", field_length=10)
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_DETAILED, "TEXT", field_length=150)   
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_CODE, "TEXT", field_length=10)   
    arcpy.AddField_management(buildings_bubd_buf_memory, FIELD_SP_ADD_INFO, "TEXT", field_length=150)   
    
    arcpy.AddMessage("Calculating SoundPLAN attributes...")
    # Name
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_NAME,
        f"!{FIELD_BUBD_FUNOGBUD}!",
        "PYTHON3"
    )

    # Road Name
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_SP_ROAD_NAME,
        f"!{FIELD_BUBD_LOKALNYID}!",
        "PYTHON3"
    )

    # Detailed
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_SP_DETAILED,
        f"!{FIELD_BUBD_FUNSZCZ}!",
        "PYTHON3"
    )

    # Code
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_SP_CODE,
        f"!{FIELD_BUBD_X_KOD}!",
        "PYTHON3"
    )

    # Additional info
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_SP_ADD_INFO,
        f"!{FIELD_BUBD_X_INFDOD}!",
        "PYTHON3"
    )

    # Floors
    arcpy.CalculateField_management(
        buildings_bubd_buf_memory,
        FIELD_SP_FLOORS,
        f"!{FIELD_BUBD_LKOND}!",
        "PYTHON3"
    )

    # Create layers to select features by the attributes
    arcpy.MakeFeatureLayer_management(buildings_bubd_buf_memory, buildings_bubd_memory_layer)

    # find buildings without floors
    arcpy.SelectLayerByAttribute_management(
        buildings_bubd_memory_layer,
        "NEW_SELECTION",
        f"{FIELD_SP_FLOORS} = 0"
    )
    arcpy.CalculateField_management(
        buildings_bubd_memory_layer,
        FIELD_SP_FLOORS,
        "1",
        "PYTHON3"
    )
    
    for building_type, sql in BUILDING_TYPES.items():
        arcpy.AddMessage(f"Searching for '{sql}'...")
        arcpy.SelectLayerByAttribute_management(
            buildings_bubd_memory_layer,
            "NEW_SELECTION",
            sql
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_SP_TYPE,
            f"{building_type}",
            "PYTHON3"
        )

    # assign AUX for not classified building 
    arcpy.SelectLayerByAttribute_management(
        buildings_bubd_memory_layer,
        "NEW_SELECTION",
        f"{FIELD_SP_TYPE} IS NULL"
    )
    arcpy.CalculateField_management(
        buildings_bubd_memory_layer,
        FIELD_SP_TYPE,
        f"{BUILDING_TYPE_AUX}",
        "PYTHON3"
    )
        
    if use_3d:
        # Set building height from buildings 3d (LOD1)
        arcpy.SelectLayerByAttribute_management(
            buildings_bubd_memory_layer,
            "NEW_SELECTION",
            f"{FIELD_ZMIN} IS NOT NULL"
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_SP_HEIGHT,
            f"!{FIELD_ZMAX}! - !{FIELD_ZMIN}!",
            "PYTHON3"
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_SP_HEIGHT_SOURCE,
            f"'{HEIGHT_SOURCE_3D}'",
            "PYTHON3"
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_SP_ELEV_SOURCE,
            f"'{HEIGHT_SOURCE_3D}'",
            "PYTHON3"
        )
        
    # Set remaining building height from number of floors
    arcpy.SelectLayerByAttribute_management(
        buildings_bubd_memory_layer,
         "SWITCH_SELECTION",
         '',
         "NON_INVERT"
    )
    arcpy.CalculateField_management(
        buildings_bubd_memory_layer,
        FIELD_SP_HEIGHT,
        f"!{FIELD_SP_FLOORS}! * 3",
        "PYTHON3"
    )
    arcpy.CalculateField_management(
        buildings_bubd_memory_layer,
        FIELD_SP_HEIGHT_SOURCE,
        f"'{HEIGHT_SOURCE_BDOT}'",
        "PYTHON3"
    )

    if use_elev:
        arcpy.AddMessage(f"Assigning elevation from '{field_elev}' to '{FIELD_ZMIN}'")
        arcpy.JoinField_management(
            buildings_bubd_buf_memory,
            FIELD_BUBD_LOKALNYID,
            buildings_elev_buf_memory,
            FIELD_BUBD_LOKALNYID,
            f"{field_elev}"
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_ZMIN,
            f"!{field_elev}!",
            "PYTHON3"
        )
        arcpy.CalculateField_management(
            buildings_bubd_memory_layer,
            FIELD_SP_ELEV_SOURCE,
            f"'{ELEV_SOURCE_NMT}'",
            "PYTHON3"
        )
        arcpy.DeleteField_management(
            buildings_bubd_buf_memory,
            field_elev
        )
        arcpy.Delete_management(buildings_elev_buf_memory)


    arcpy.AddMessage("Deleting unnecessary fields...")
    # leave following original BUBD fields:
    fields_bubd.remove(FIELD_BUBD_OBJECTID)
    fields_bubd.remove(FIELD_SHAPE)
    fields_bubd.remove(FIELD_BUBD_TERYT)
    arcpy.DeleteField_management(buildings_bubd_buf_memory, fields_bubd)    

    if no_holes:
        # Divide polygons with holes using tesselation
        arcpy.AddMessage("Dividing polygons with holes...")
        arcpy.CalculateGeometryAttributes_management(
            buildings_bubd_buf_memory,
            [[FIELD_HOLES, "HOLE_COUNT"]]
        )
        arcpy.SelectLayerByAttribute_management(
            buildings_bubd_memory_layer,
            "NEW_SELECTION",
            f"{FIELD_HOLES} > 0"
        )

        tessellation_fc = r"in_memory\tesselation"
        buildings_with_holes_fc = r"in_memory\buildings_with_holes"
        building_to_tessellate_fc = r"in_memory\building_to_tessellate"
        buildings_intersect_tessellation_fc = r"in_memory\buildings_intersect_tessellation"
        buildings_intersect_tessellation_single_fc = r"in_memory\buildings_intersect_tessellation_single"

        arcpy.CreateFeatureclass_management(
            building_to_tessellate_fc.split("\\")[0],
            building_to_tessellate_fc.split("\\")[1],
            "POLYGON",
            buildings_bubd_buf_memory,
            spatial_reference=arcpy.Describe(buildings_bubd_buf_memory).spatialReference
        )
        
        arcpy.Select_analysis(buildings_bubd_memory_layer, buildings_with_holes_fc)
        arcpy.DeleteFeatures_management(buildings_bubd_memory_layer)

        fields = [f.name for f in arcpy.ListFields(buildings_with_holes_fc) if f.type not in ['Geometry']]
        fields.append("SHAPE@")

        with arcpy.da.SearchCursor(buildings_with_holes_fc, fields) as search_cursor:
            for row in search_cursor:

                arcpy.AddMessage(f"Building '{row[0]}' Tessellation...")

                shape = row[len(row)-1]
                spatial_ref = shape.spatialReference
                area = shape.area
                size = calc_tessellation_size(shape, spatial_ref, area)
                
                arcpy.GenerateTessellation_management(
                    tessellation_fc,
                    shape.extent,
                    "TRIANGLE",
                    size,
                    spatial_ref
                )

                insert_cursor = arcpy.da.InsertCursor(building_to_tessellate_fc, fields)
                insert_cursor.insertRow(row)
                del insert_cursor
            
                arcpy.PairwiseIntersect_analysis([building_to_tessellate_fc, tessellation_fc], buildings_intersect_tessellation_fc)
                arcpy.MultipartToSinglepart_management(buildings_intersect_tessellation_fc, buildings_intersect_tessellation_single_fc)
                
                # add tessellated building to main dataset
                arcpy.Append_management(buildings_intersect_tessellation_single_fc, buildings_bubd_buf_memory, "NO_TEST")

                # clean memory
                arcpy.DeleteFeatures_management(building_to_tessellate_fc)
                arcpy.Delete_management(tessellation_fc)
                arcpy.Delete_management(buildings_intersect_tessellation_fc)
                arcpy.Delete_management(buildings_intersect_tessellation_single_fc)

        arcpy.Delete_management(buildings_with_holes_fc)
            
    arcpy.AddMessage(f"Saving {buildings_out}...")
    try:
        arcpy.Select_analysis(buildings_bubd_buf_memory, buildings_out)
    except Exception as e:
        arcpy.AddError(str(e))

    arcpy.Delete_management(buildings_bubd_buf_memory)
    arcpy.AddMessage("Done")
    
    return

def get_hole_count(geom):
    hole_count = 0
    try:
        for part in geom:
            for pnt in part:
                if not pnt:
                    hole_count+=1
    except:
        pass
    return hole_count

def calc_tessellation_size(polygon, spatial_ref, size):
    """Pre-tessellation on geometry objects to estimate optimal tessellation size."""

    tessellation_shapes = arcpy.GenerateTessellation_management(
        arcpy.Geometry(),
        polygon.extent,
        "TRIANGLE",
        size,
        spatial_ref
    )
    tessellation_shapes.append(polygon)
    intersect_shapes = arcpy.Intersect_analysis(tessellation_shapes, arcpy.Geometry())

    for shape in intersect_shapes:
        n = get_hole_count(shape)
        if n > 0:
            return calc_tessellation_size(polygon, spatial_ref, size * TESSELLATION_SIZE_FACTOR)
    
    return size


# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    # Tool parameter accessed with GetParameter or GetParameterAsText
    buildings_bubd = arcpy.GetParameterAsText(0)
    if not buildings_bubd:
        buildings_bubd = r"<feature class with BDOT buildings>"
        
    buildings_3d = arcpy.GetParameterAsText(1)
    if not buildings_3d:
        buildings_3d = r"<feature class with 3D buildings(LOD)>"
    
    buildings_elev = arcpy.GetParameterAsText(2)
    if not buildings_elev:
        buildings_elev = r"<feature class with building elevation>"
    
    field_elev = arcpy.GetParameterAsText(3)
    if not field_elev:
        field_elev = "<attribute field name with building elevation>"
    
    buffer_in = arcpy.GetParameterAsText(4)
    if not buffer_in:
        buffer_in = r"feature class with area of interest"
    
    buildings_out = arcpy.GetParameterAsText(5)
    if not buildings_out:
        buildings_out = r"<output feature class with processed building>"
    
    no_holes = arcpy.GetParameter(6)

    soundplan_prepare_buildings(
        buildings_bubd,
        buildings_3d,
        buildings_elev,
        field_elev,
        buffer_in,
        buildings_out,
        no_holes
    )
        