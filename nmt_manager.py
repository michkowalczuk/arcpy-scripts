import arcpy
import math
import os


# exceptionally, in this script, the comments are in Polish

# warstwy ASCII TBD 
# http://www.gugik.gov.pl/pzgik/zamow-dane/dane-pomiarowe
# 1. p - punkty siatki
# 2. j - obszary planarne
# 3. c - cieki
# 4. k - punkty (koty) wysokościowe
# 5. o - obiekty inżynieryjne
# 6. pz - punkty na obszarach wydzielonych
# 7. s - linie nieciągłości
# 8. sz - linie nieciągłości w obszarach wydzieleń
# 9. z - obszary wydzielone (o obniżonej dokładności np. lasy)
POINT_SIGNS = ['p', 't', 'pz', 'k']
LINE_SIGNS = ['w', 's', 'c', 'sz', 'j', 'z', 'o']

# in-memory fc names
MEM_WORKSPACE = "in_memory"  # new "memory" workspace error
MEM_NMT_POINTS_TEMP ="nmtPointsTemp"
MEM_NMT_LINES_TEMP = "nmtLinesTemp"
MEM_NMT_ENVELOPES_TEMP = "nmtEnvelopesTemp"
MEM_NMT_LINES_TEMP_CLIP = "nmtLinesTempClip"
MEM_NMT_POINTS = "nmtPoints"
MEM_NMT_LINES = "nmtLines"
MEM_NMT_ENVELOPES = "nmtEnvelopes"
MEM_NMT_INDEX_AREA = "nmtIndexArea"
MEM_CLIP_AREA = "clipArea"

# layer names
LYR_NMT_POINTS_TEMP = "nmtPointsTempLyr"
LYR_INDEX_AREA = "nmtIndexAreaLyr"
LYR_NMT_POINTS = "nmtPointsLyr"
LYR_NMT_LINES = "nmtLineslinesLyr"

# fields
FLD_INDEX_UNIFIED = "GODLO_UNIFIED"
FLD_INDEX = "GODLO"
FLD_LAYER = "WARSTWA"
FLD_WARNINGS = "UWAGI"
FLD_SHAPE_XY = "SHAPE@XY"
FLD_SHAPE_Z = "SHAPE@Z"
FLD_SHAPE = "SHAPE@"

# PUWG92
EPSG_102173 = 102173
EPSG_2180 = 2180

ENVELOPE_EDGE_BUFFER = "1 Meters"
EPSILON = 0.005
SEPARATOR_LENGTH = 80
SEPARATOR_SIGN = "="

# message types
MSG_MESSAGE = "MESSAGE"
MSG_WARNING = "WARNING"
MSG_ERROR = "ERROR"

OUT_POINTS = "points"
OUT_LINES = "lines"
OUT_ENVELOPES = "envelopes"
OUT_BRIDGES = "bridges"
OUT_RAW_POINTS = "raw_points"
OUT_RAW_LINES = "raw_lines"

def add_arcpy_message(message, separator=False, type=MSG_MESSAGE):
    if separator:
        add_message_separator(SEPARATOR_SIGN)

    type_up = type.upper()    

    if type_up in (MSG_MESSAGE, "MSG", "M"):
        arcpy.AddMessage(message)
    elif type_up in (MSG_WARNING, "WRN", "W"):
        arcpy.AddWarning(message)
    elif type_up in (MSG_ERROR, "ERR", "E"):
        arcpy.AddError(message)

def generate_separator(separator):
    return separator * SEPARATOR_LENGTH

def add_message_separator(separator):
    arcpy.AddMessage(generate_separator(separator))

def get_asc_files_dict(tbd_folder):

    # old version: ascFiles = [f for f in os.listdir(tbd_folder) if f.lower().endswith('.asc')]
    
    asc_files_dict = {}
    for root, _, files in os.walk(tbd_folder):
        for file in files:
            if(file.lower().endswith(".asc")):
                file_no_extension = file.split(".")[0]
                asc_files_dict[file_no_extension] = os.path.join(root, file)
    return asc_files_dict
    
class Extent:
    '''A class represent an object extent'''
    def __init__(self):
        self.reset()

    def is_empty(self):
        return math.isnan(self.x_min) or math.isnan(self.y_min)

    def reset(self):
        self.x_min = float('NaN')
        self.y_min = float('NaN')
        self.x_max = float('NaN')
        self.y_max = float('NaN')

    def get_line_type(self):
        if abs(self.x_max - self.x_min) < EPSILON:
            return "all_vertical"
        elif abs(self.y_max - self.y_min) < EPSILON:
            return "all_horizontal"
        else: 
            return ""

    def update(self, x, y):
        if math.isnan(self.x_min) or math.isnan(self.y_min):
            self.x_min = self.x_max = x
            self.y_min = self.y_max = y
        else:
            if x < self.x_min:
                self.x_min = x
            if x > self.x_max:
                self.x_max = x
            if y < self.y_min:
                self.y_min = y
            if y > self.y_max:
                self.y_max = y

def parse_xyz_line(line):
    floats = [float(x) for x in line.split()]
    
    # x/y w plikach ascii maja odwrocona kolejnosc
    #? wyprowadzic jako parametr odwrocenie XY
    x = floats[1]
    y = floats[0]
    z = floats[2]

    return x, y, z

def set_arcpy_environment(workspace, spatial_ref):
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = workspace
    arcpy.env.cartographicCoordinateSystem = spatial_ref

def get_out_fc_names(workspace, prefix):
    workspace_desc = arcpy.Describe(workspace) 
    if workspace_desc.dataType == "Folder":
        ext = ".shp"
    else:
        ext = ""

    out_fc_names = {}
    out_fc_names[OUT_POINTS] = f"{prefix}_NMT_punkty{ext}"
    out_fc_names[OUT_LINES] = f"{prefix}_NMT_linie{ext}"
    out_fc_names[OUT_ENVELOPES] = f"{prefix}_NMT_obrysy{ext}"
    out_fc_names[OUT_BRIDGES] = f"{prefix}_NMT_obiekty{ext}"
    out_fc_names[OUT_RAW_POINTS] = f"{prefix}_punkty_surowe{ext}"
    out_fc_names[OUT_RAW_LINES] = f"{prefix}_linie_surowe{ext}"
    
    return out_fc_names

def delete_existing_fc(out_fc_names):
    add_arcpy_message(f"Usuwanie istniejących plików...", True)
    
    for fc in out_fc_names.values():
        if arcpy.Exists(fc):
            add_arcpy_message(f"usuwanie: {fc}")
            arcpy.Delete_management(fc)

def get_indexes_set(asc_files_dict):
    """Gets set of unique indexes"""

    indexes = set([asc_file_name.split('_')[0] for asc_file_name in asc_files_dict.keys()])
    message = "Odnalezione godla:\n"
    message += "\n".join(indexes)
    add_arcpy_message(message, separator=True)
    
    return indexes

def unify_index(index):
    """
    Upraszczanie i unifikowanie godla:
    "N-33-132-A-c-2-2" do postaci "n33132ac22"
    Dodatkowo przycinanie prefixu "NMT-"
    """
    index_unified = (("").join(index.split("-"))).lower()
    if index_unified.startswith("nmt"):
        index_unified = index_unified.split("nmt")[1]
    
    return index_unified

def get_index_key (index, sign):
    return f"{index}_{sign}"

def get_line_type(array):
    extent = Extent()
    [extent.update(point.X, point.Y) for point in array]

    return extent.get_line_type()

   
def delete_lines_on_envelopes(nmt_lines_fc, nmt_envelopes_fc, spatial_ref_92):
    """
    Usuwanie lini wzdluz krawedzi obrysow:
    * self-intersect na skorowidzach, aby otrzymac linie podzialu ("MEM_NMT_ENELOPES_SELF_INTERSECT")
    * agregacja linii ("nmtEnvelopesSelfInterDis") ?? nieporzebne
    * bufor z tych linii o wielkosci 1 m ("MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS")
    * selekcja przestrzenna typu INTERSECT linii przecinajacych sie z buforem
    * zapis selekcji do nowego zbioru ("MEM_NMT_LINES_ON_ENVELOPES")
    * usuniecie selekcji z oryginalu 
    * rozbicie wyodrebnionych polilinii na linie (MEM_NMT_LINES_ON_ENVELOPES_SPLIT)
    * selekcja linii spoza bufora i zwrocenie ich do zbioru glownego linii ("splitted")
    """
    MEM_NMT_ENELOPES_SELF_INTERSECT = "nmtEnvelopesSelfIntersect"
    MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS = "nmtEnvelopesSelfIntersectBufDis"
    MEM_NMT_LINES_ON_ENVELOPES = "nmtLinesOnEnvelopes"
    MEM_NMT_LINES_ON_ENVELOPES_SPLIT = "nmtLinesOnEnvelopesSplit"
    
    LYR_NMT_LINES_ON_ENVELOPES_SPLIT = "nmtLinesOnEnvelopesSplitLyr"

    nmt_lines_on_envelopes_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_LINES_ON_ENVELOPES}"
    nmt_lines_on_envelopes_split_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_LINES_ON_ENVELOPES_SPLIT}"

    add_arcpy_message("Usuwanie linii wzdłuż krawędzi skorowidzów...", True)

    arcpy.Intersect_analysis(
        nmt_envelopes_fc,
        f"{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT}",
        "ONLY_FID", "#", "LINE")
    
    arcpy.Buffer_analysis(
        f"{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT}",
        f"{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS}",
        ENVELOPE_EDGE_BUFFER,
        "FULL", "ROUND", "ALL", "#")

    arcpy.SelectLayerByLocation_management(
        LYR_NMT_LINES,
        "INTERSECT",
        f"{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS}")

    arcpy.Select_analysis(LYR_NMT_LINES, nmt_lines_on_envelopes_fc)

    # usun zaznaczenie
    arcpy.DeleteFeatures_management(LYR_NMT_LINES)

    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_LINES_ON_ENVELOPES_SPLIT,
        "POLYLINE",
        nmt_lines_on_envelopes_fc,
        "DISABLED",
        "ENABLED",
        spatial_ref_92)

    insert_cursor = arcpy.da.InsertCursor(
        nmt_lines_on_envelopes_split_fc,
        [FLD_SHAPE, FLD_LAYER, FLD_INDEX, FLD_WARNINGS])

    with arcpy.da.SearchCursor(
        nmt_lines_on_envelopes_fc,
        [FLD_SHAPE, FLD_LAYER, FLD_INDEX, FLD_WARNINGS]) as search_cursor:
        for row in search_cursor:
            sign = row[1]
            index = row[2]
            partnum = 0

            # Step through each part of the feature
            for part in row[0]:
                # Step through each vertex in the feature
                prevX = None
                prevY = None
                prevZ = None
                for pnt in part:
                    if pnt:
                        if prevX:
                            line_array = arcpy.Array(
                                [arcpy.Point(prevX, prevY, prevZ), arcpy.Point(pnt.X, pnt.Y, pnt.Z)])
                            line = arcpy.Polyline(line_array, spatial_ref_92, True)
                            insert_cursor.insertRow((line, sign, index, 'splitted'))
                        prevX = pnt.X
                        prevY = pnt.Y
                        prevZ = pnt.Z
                    else:
                        pass
                partnum += 1

    del insert_cursor

    # --------------------------------------------------------------------------------

    arcpy.MakeFeatureLayer_management(
        nmt_lines_on_envelopes_split_fc,
        LYR_NMT_LINES_ON_ENVELOPES_SPLIT)
    arcpy.SelectLayerByLocation_management(
        LYR_NMT_LINES_ON_ENVELOPES_SPLIT,
        'WITHIN',
        f'{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS}')
    arcpy.SelectLayerByLocation_management(
        LYR_NMT_LINES_ON_ENVELOPES_SPLIT,
        'INTERSECT',
        f'{MEM_WORKSPACE}\\{MEM_NMT_ENELOPES_SELF_INTERSECT_BUF_DIS}',
        '#', 'SWITCH_SELECTION')

    arcpy.Append_management([LYR_NMT_LINES_ON_ENVELOPES_SPLIT], nmt_lines_fc, "NO_TEST")

    return

def extract_shp_from_tbd(
    tbd_folder_in,
    workspace_out, 
    prefix_out,
    spatial_ref_out,
    clip_area_in,
    nmt_index_area_in,
    import_points, 
    import_lines,
    export_raw_data):

    # initialization
    set_arcpy_environment(workspace_out, spatial_ref_out)
    out_fc_names = get_out_fc_names(workspace_out, prefix_out)
    delete_existing_fc(out_fc_names)

    #? get from index area fc
    spatial_ref_92 = arcpy.SpatialReference(EPSG_2180)
    
    # paths to in-memory feature classes
    nmt_points_temp_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_POINTS_TEMP}"
    nmt_lines_temp_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_LINES_TEMP}"
    nmt_envelopes_temp_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_ENVELOPES_TEMP}"
    nmt_lines_temp_clip_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_LINES_TEMP_CLIP}"
    # nmtBridgesTempFC = r'in_memory\nmtBridgesTemp'

    nmt_points_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_POINTS}"
    nmt_lines_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_LINES}"
    nmt_envelopes_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_ENVELOPES}"
    nmt_index_area_fc = f"{MEM_WORKSPACE}\\{MEM_NMT_INDEX_AREA}"
    clip_area_fc = f"{MEM_WORKSPACE}\\{MEM_CLIP_AREA}"

    # nmtPolylinesIntersectFC = r'in_memory\nmtLinesIntersect'
    
    # Przygotowywanie zbiorów w pamieci oraz odpowiadajacych im warstw
    # CLIP AREA
    arcpy.CopyFeatures_management(clip_area_in, clip_area_fc)
    
    # NMT INDEX AREA
    arcpy.CopyFeatures_management(nmt_index_area_in, nmt_index_area_fc)

    # aby wyszkuiwac po godle nalezy stworzyc ujednolicony jego format:
    # * bez myslnikow
    # * male litery
    # * tylko indels godla, bez przedrostka "nmt"
    arcpy.AddField_management(nmt_index_area_fc, FLD_INDEX_UNIFIED, 'TEXT', '#', '#', 15)
    code = """def unify_symbol(symbol):
    symbol_unified = (("").join(symbol.split("-"))).lower()
    if symbol_unified.startswith("nmt"):
        symbol_unified = symbol_unified.split("nmt")
    return symbol_unified"""
    arcpy.CalculateField_management(
        nmt_index_area_fc,
        FLD_INDEX_UNIFIED,
        f"unify_symbol(!{FLD_INDEX}!)",
        "PYTHON3",
        code)

    # Tworzenie tymczasowych zbiorow w pamieci do przechowywania danych z aktualnie przetwarzanego godla
    # NMT POINTS TEMP
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_POINTS_TEMP,
        'POINT',
        '#',
        'DISABLED',
        'ENABLED',
        spatial_ref_92)
    arcpy.AddField_management(nmt_points_temp_fc, FLD_LAYER, 'TEXT', '#', '#', 2)
    arcpy.AddField_management(nmt_points_temp_fc, FLD_INDEX, 'TEXT', '#', '#', 15)

    # NMT LINES TEMP
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_LINES_TEMP,
        'POLYLINE',
        '#',
        'DISABLED',
        'ENABLED',
        spatial_ref_92)
    arcpy.AddField_management(nmt_lines_temp_fc, FLD_LAYER, 'TEXT', '#', '#', 2)
    arcpy.AddField_management(nmt_lines_temp_fc, FLD_INDEX, 'TEXT', '#', '#', 15)
    arcpy.AddField_management(nmt_lines_temp_fc, FLD_WARNINGS, 'TEXT', '#', '#', 15)

    # NMT ENVELOPES TEMP
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_ENVELOPES_TEMP,
        'POLYGON',
        '#',
        'DISABLED',
        'ENABLED',
        spatial_ref_92)
    arcpy.AddField_management(nmt_envelopes_temp_fc, FLD_INDEX, 'TEXT', '#', '#', 15)
    arcpy.AddField_management(nmt_envelopes_temp_fc, FLD_INDEX_UNIFIED, 'TEXT', '#', '#', 15)

    # Tworzenie zbiorow w pamieci do przwchowywania wszystkich danych
    # szablon z tymczasowych TEMP
    # NMT POINTS 
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_POINTS,
        'POINT',
        nmt_points_temp_fc,
        'DISABLED', 
        'ENABLED',
        spatial_ref_92)

    # NMT LINES    
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_LINES,
        'POLYLINE',
        nmt_lines_temp_fc,
        'DISABLED',
        'ENABLED',
        spatial_ref_92)
    
    # NMT ENVELOPES
    arcpy.CreateFeatureclass_management(
        MEM_WORKSPACE,
        MEM_NMT_ENVELOPES,
        'POLYGON',
        nmt_envelopes_temp_fc,
        'DISABLED',
        'ENABLED',
        spatial_ref_92)

    # RAW DATA
    if export_raw_data:
        arcpy.CreateFeatureclass_management(
            workspace_out,
            out_fc_names[OUT_RAW_POINTS],
            'POINT',
            nmt_points_temp_fc,
            'DISABLED', 
            'ENABLED',
            spatial_ref_92)
        arcpy.CreateFeatureclass_management(
            workspace_out,
            out_fc_names[OUT_RAW_LINES],
            'POLYLINE',
            nmt_lines_temp_fc,
            'DISABLED',
            'ENABLED',
            spatial_ref_92)

    # Tworzenie warstw
    arcpy.MakeFeatureLayer_management(nmt_index_area_fc, LYR_INDEX_AREA)
    arcpy.MakeFeatureLayer_management(nmt_points_fc, LYR_NMT_POINTS)
    arcpy.MakeFeatureLayer_management(nmt_lines_fc, LYR_NMT_LINES)

    # Tworzenie kursorow do zbiorow tymczasowych
    points_temp_cursor = arcpy.da.InsertCursor(
        nmt_points_temp_fc,
        [FLD_SHAPE_XY, FLD_SHAPE_Z, FLD_LAYER, FLD_INDEX])
    lines_temp_cursor = arcpy.da.InsertCursor(
        nmt_lines_temp_fc,
        [FLD_SHAPE, FLD_LAYER, FLD_INDEX, FLD_WARNINGS])
    # envelopeCursor = arcpy.da.InsertCursor(nmtEnvelopesTempFC, [FIELD_SHAPE, FIELD_INDEX])

    # słownik nazw plikow oraz ich sciezek
    asc_files_dict = get_asc_files_dict(tbd_folder_in)

    # ze wszystkich plikow .ASC wybieramy tylko unikalne godla
    indexes = get_indexes_set(asc_files_dict)

    extent = Extent()
    arcpy_array = arcpy.Array()
    index_count = len(indexes)
    for i, index in enumerate(indexes):
        add_arcpy_message(f"Przetwarzanie godla {i+1} z {index_count}: {index}...", True)

        index_unified = unify_index(index)

        extent.reset()
        # ---------------------------------------------------------------------
        # PUNKTY
        # ---------------------------------------------------------------------
        if import_points:
            add_arcpy_message("Przetwarzanie punktów...", True)
            for point_sign in POINT_SIGNS:
                
                index_key = get_index_key(index, point_sign)
                if index_key not in asc_files_dict:
                    continue

                point_asc_file_path = asc_files_dict[index_key]
                if os.path.exists(point_asc_file_path):
                    point_asc_file = open(point_asc_file_path, "r")

                    for asc_line in point_asc_file.readlines():
                        try:  # try nie pogarsza wydajnosci
                            x, y, z = parse_xyz_line(asc_line)
                            points_temp_cursor.insertRow(((x, y), z, point_sign, index_unified))

                            # okreslanie min/max do obrysu
                            extent.update(x, y)
                        except:
                            exc_message = f"{point_asc_file_path} - napotkano na blad konwersji linii: {asc_line}"
                            add_arcpy_message(exc_message, message=MSG_ERROR)

                    add_arcpy_message(point_asc_file_path + ' - przekonwertowano')
                else:
                    add_arcpy_message(point_asc_file_path + ' - nie odnaleziono', message=MSG_WARNING)

        # ---------------------------------------------------------------------
        # POLILINIE i POLIGONY
        # ---------------------------------------------------------------------
        # poligony importowane jako polilinie ze wzgledu na poziome i pionowe linie oddzielajace arkusze
        # linie poziome i pionowe oddzielane w celu poniejszego odfiltrowania

        if import_lines:
            add_arcpy_message("Przetwarzanie polilini...", separator=True)
            for line_sign in LINE_SIGNS:

                index_key = get_index_key(index, line_sign)
                if index_key not in asc_files_dict:
                    continue

                line_asc_file_path = asc_files_dict[index_key]
                if os.path.exists(line_asc_file_path):
                    line_asc_file = open(line_asc_file_path, "r")

                    for iLine, asc_line in enumerate(line_asc_file.readlines()):
                        try:
                            if "Start" in asc_line:
                                # nowy obiekt liniowy
                                arcpy_array.removeAll()
                                # extent.reset()
                            elif "End" in asc_line:
                                # koniec obiektu
                                # aby utworzyc polilinie potrzeba wiecej niz 1 wierzcholek
                                if arcpy_array.count < 2:
                                    continue

                                # check if extent is horizontal, vertical or none 
                                line_type = get_line_type(arcpy_array)

                                if line_type:
                                    add_arcpy_message(
                                        f"{line_asc_file_path} - odnaleziona horyzontalna lub wertykalna linia (linia nr {iLine+1})",
                                        type=MSG_WARNING
                                    )

                                lines_temp_cursor.insertRow(
                                    (arcpy.Polyline(arcpy_array, spatial_ref_92, True),
                                    line_sign,
                                    index_unified,
                                    line_type))
                            elif '\n' == asc_line:  
                                continue      
                            else:
                                x, y, z = parse_xyz_line(asc_line)
                                arcpy_array.add(arcpy.Point(x, y, z))

                                extent.update(x, y)
                        except:
                            exc_message = f"{line_asc_file_path} - napotkano na blad w linii {iLine+1}: {asc_line}"
                            add_arcpy_message(exc_message, type=MSG_ERROR)

                    add_arcpy_message(f"{line_asc_file_path} - przekonwertowano")
                else:
                    add_arcpy_message(f"{line_asc_file_path} - nie odnaleziono", message=MSG_WARNING)

        # sprawdzamy czy dla danego godla/pliku sa dane
        if extent.is_empty():
            continue
        
        # ------------------------------------------------------------------------------
        
        add_arcpy_message("Dodawanie danych z aktualnego godla do zbioru danych...", separator=True)
        
        # przerzucanie danych do zbiorow wlasciwych
        select_query = f""""{FLD_INDEX_UNIFIED}" = '{index_unified}'"""
        arcpy.SelectLayerByAttribute_management(LYR_INDEX_AREA, "NEW_SELECTION", select_query)
        arcpy.Append_management([LYR_INDEX_AREA], nmt_envelopes_temp_fc, 'NO_TEST')

        # usuwanie duplikatow ze zbioru
        # wybieranie danych wewnatrz obrysu skorowidzu
        if import_points:
            add_arcpy_message('# punkty...', separator=False)
            
            arcpy.MakeFeatureLayer_management(nmt_points_temp_fc, LYR_NMT_POINTS_TEMP)
            arcpy.SelectLayerByLocation_management( LYR_NMT_POINTS_TEMP, 'INTERSECT', LYR_INDEX_AREA)
            arcpy.Append_management([LYR_NMT_POINTS_TEMP], nmt_points_fc)

        if import_lines:
            add_arcpy_message('# linie...', separator=False)
            # usuwanie linii-duplikatow ze zbioru
            arcpy.Clip_analysis(nmt_lines_temp_fc, LYR_INDEX_AREA, nmt_lines_temp_clip_fc)
            arcpy.Append_management([nmt_lines_temp_clip_fc], nmt_lines_fc)

        if export_raw_data:
            if import_points: arcpy.Append_management([nmt_points_temp_fc], out_fc_names[OUT_RAW_POINTS])  
            if import_lines: arcpy.Append_management([nmt_lines_temp_fc], out_fc_names[OUT_RAW_LINES])  
            
        # wyczyszczenie zbiorow tymczasowych do nastepnej kolejki
        arcpy.DeleteFeatures_management(nmt_points_temp_fc)
        arcpy.DeleteFeatures_management(nmt_lines_temp_fc)

    arcpy.Append_management([nmt_envelopes_temp_fc], nmt_envelopes_fc)

    # ------------------------------------------------------------------------------
    
    # zwalnianie zasobów
    add_arcpy_message("Zwalnianie tymczasowych zasobów...", True)
    del points_temp_cursor
    del lines_temp_cursor
    arcpy.Delete_management(nmt_points_temp_fc)
    arcpy.Delete_management(nmt_lines_temp_fc)
    arcpy.Delete_management(nmt_lines_temp_clip_fc)
    arcpy.Delete_management(nmt_envelopes_temp_fc)

    if import_lines:
        delete_lines_on_envelopes(nmt_lines_fc, nmt_envelopes_fc, spatial_ref_92)
    
    # ostatki
    add_arcpy_message("Wybieranie danych wewnatrz obszaru zaineresowania...", separator=True)

    # CLIP AREA
    # PUNKTY
    if import_points:
        add_arcpy_message('# punkty...', separator=False)
        arcpy.SelectLayerByLocation_management(LYR_NMT_POINTS, "INTERSECT", clip_area_fc)
    # POLILINIE
    if import_lines:
        add_arcpy_message('# linie...', separator=False)
        arcpy.SelectLayerByLocation_management(LYR_NMT_LINES, "INTERSECT", clip_area_fc)
        # nie wybieraj obiektow
        arcpy.SelectLayerByAttribute_management(LYR_NMT_LINES, "SUBSET_SELECTION", f""""{FLD_LAYER}" <> 'o'""")
    
    # If in/out CS is the same, only copy data
    if spatial_ref_out.PCSCode == EPSG_2180 or spatial_ref_out.PCSCode == EPSG_102173:
        add_arcpy_message('Zapisywanie do katalogu docelowego...', separator=True)
        # kopiowanie do katalogu wyjsciowego
        arcpy.CopyFeatures_management(nmt_envelopes_fc, out_fc_names[OUT_ENVELOPES])
        # PUNKTY
        if import_points:
            add_arcpy_message('# punkty...', separator=False)
            arcpy.CopyFeatures_management(LYR_NMT_POINTS, out_fc_names[OUT_POINTS])
        # POLILINIE
        if import_lines:
            add_arcpy_message('# linie...', separator=False)
            arcpy.CopyFeatures_management(LYR_NMT_LINES, out_fc_names[OUT_LINES])
            # OBIEKTY
            add_arcpy_message('Wyodrebnianie obiektow inzynieryjnych...', separator=True)
            arcpy.SelectLayerByLocation_management(LYR_NMT_LINES, "INTERSECT", clip_area_fc)
            arcpy.SelectLayerByAttribute_management(LYR_NMT_LINES, "SUBSET_SELECTION", f""""{FLD_LAYER}" = 'o'""")
            arcpy.CopyFeatures_management(LYR_NMT_LINES, out_fc_names[OUT_BRIDGES])
    # otherwise, project data
    else:
        add_arcpy_message('Zapisywanie do katalogu docelowego + reprojekcja...', separator=True)
        arcpy.Project_management(nmt_envelopes_fc, out_fc_names[OUT_ENVELOPES], spatial_ref_out)
        # PUNKTY
        if import_points:
            add_arcpy_message('# punkty...', separator=False)
            arcpy.Project_management(LYR_NMT_POINTS, out_fc_names[OUT_POINTS], spatial_ref_out)
        # POLILINIE
        if import_lines:
            add_arcpy_message('# linie...', separator=False)
            arcpy.Project_management(LYR_NMT_LINES, out_fc_names[OUT_LINES], spatial_ref_out)
            # OBIEKTY
            add_arcpy_message('Wyodrebnianie obiektow inzynieryjnych...', separator=True)
            arcpy.SelectLayerByLocation_management(LYR_NMT_LINES, 'INTERSECT', clip_area_fc)
            arcpy.SelectLayerByAttribute_management(LYR_NMT_LINES, 'SUBSET_SELECTION', '"TYP" = \'o\'')
            arcpy.Project_management(LYR_NMT_LINES, out_fc_names[OUT_BRIDGES], spatial_ref_out)

    add_arcpy_message("Zakończono powodzeniem", True)
    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    development = (arcpy.GetArgumentCount() == 0) and (arcpy.GetParameter(0) is None)
    
    if development:
        add_arcpy_message('Skrypt uruchomiony w trybie "DEVELOPMENT"', True)
        tbd_folder_in = r"<TBD folder>"
        workspace_out = r"<output workspace>"
        prefix_out = "xEVRF_2km_pionowe_poziome"
        spatial_ref_out = arcpy.SpatialReference(2180)
        clip_area_in = r"<shapefile with area of interest>"
        nmt_index_area_in = r"<shapefile with NMT indexes>"
        import_points = True
        import_lines = True
        export_raw_data = True
    else:
        # Tool parameter accessed with GetParameter or GetParameterAsText
        tbd_folder_in = arcpy.GetParameterAsText(0)
        workspace_out = arcpy.GetParameterAsText(1)
        prefix_out = arcpy.GetParameterAsText(2)
        spatial_ref_out = arcpy.GetParameter(3)
        clip_area_in = arcpy.GetParameterAsText(4)
        nmt_index_area_in = arcpy.GetParameterAsText(5)
        import_points = arcpy.GetParameter(6)
        import_lines = arcpy.GetParameter(7)
        export_raw_data = arcpy.GetParameter(8)

    extract_shp_from_tbd(
        tbd_folder_in,
        workspace_out, 
        prefix_out,
        spatial_ref_out,
        clip_area_in,
        nmt_index_area_in,
        import_points, 
        import_lines,
        export_raw_data)
    