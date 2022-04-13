import arcgisscripting
import arcpy
from arcpy.conversion import AddRasterToGeoPackage
from arcpy.management import AddSpatialIndex
import utils
import os


def bdot_manager(
    folder_in,
    recursive_search,
    workspace_out,
    spatial_ref_out,
    clip_area_in,
    continue_process):

    utils.set_arcpy_environment(workspace_out, spatial_ref_out)
    utils.replace_dots_in_paths(folder_in, "_")

    workspace_is_folder = utils.is_workspace_folder(workspace_out)

    bdot_folders = []
    if recursive_search:
        for root, directories, _ in os.walk(folder_in):
            for directory in directories:
                bdot_folders.append(os.path.join(root, directory))
    else:
        bdot_folders = folder_in.split(";")

    bdot_classes = {
        'SWRS': 'rzeka_i_strumien',
        'SWKN': 'kanal',
        'SWRM': 'row_melioracyjny',
        'SKJZ': 'jezdnia',
        'SKDR': 'droga',
        'SKRW': 'rondo_i_wezel_drogowy',
        'SKRP': 'ciag_ruchu_pieszego_i_rowerowego',
        'SKTR': 'tor_lub_zespol_torow',
        'SKPP': 'przeprawa',
        'SULN': 'linia_napowietrzna',
        'SUPR': 'przewod_rurowy',
        'PTWP': 'woda_powierzchniowa',
        'PTZB': 'zabudowa',
        'PTLZ': 'teren_lesny_i_zadrzewiony',
        'PTRK': 'roslinnosc_krzewiasta',
        'PTUT': 'uprawa_trwala',
        'PTTR': 'roslinnosc_trawiasta_i_uprawa_rolna',
        'PTKM': 'teren_pod_drogami_kolowymi_szynowymi_i_lotniskowymi',
        'PTGN': 'grunt_nieuzytkowany',
        'PTPL': 'plac',
        'PTSO': 'skladowisko_odpadow',
        'PTWZ': 'wyrobisko_i_zwalowisko',
        'PTNZ': 'pozostaly_teren_niezabudowany',
        'BUBD': 'budynek',
        'BUIN': 'budowla_inzynierska',
        'BUHD': 'budowla_hydrotechniczna',
        'BUSP': 'budowla_sportowa',
        'BUWT': 'wysoka_budowla_techniczna',
        'BUZT': 'zbiornik_techniczny',
        'BUUO': 'umocnienie_drogowe_kolejowe_i_wodne',
        'BUZM': 'budowla_ziemna',
        'BUTR': 'urzadzenie_transportowe',
        'BUIT': 'inne_urzadzenie_techniczne',
        'BUCM': 'budowla_cmentarna',
        'BUIB': 'inna_budowla',
        'KUMN': 'kompleks_mieszkaniowy',
        'KUPG': 'kompleks_przemyslowo_uslugowy',
        'KUHU': 'kompleks_handlowo_uslugowy',
        'KUKO': 'kompleks_komunikacyjny',
        'KUSK': 'kompleks_sportowy_i_rekreacyjny',
        'KUHO': 'kompleks_uslug_hotelarskich',
        'KUOS': 'kompleks_oswiatowy',
        'KUOZ': 'kompleks_ochrony_zdrowia_i_opieki_spolecznej',
        'KUZA': 'kompleks_zabytkowo_historyczny',
        'KUSC': 'kompleks_sakralny_i_cmentarz',
        'KUIK': 'inny_kompleks_uzytkowania_terenu',
        'TCON': 'obszar_Natura_2000',
        'TCPK': 'park_krajobrazowy',
        'TCPN': 'park_narodowy',
        'TCRZ': 'rezerwat',
        'ADJA': 'jednostka_podzialu_administracyjnego',
        'ADMS': 'miejscowosc',
        'OIPR': 'obiekt_przyrodniczy',
        'OIKM': 'obiekt_zwiazany_z_komunikacja',
        'OIOR': 'obiekt_o_znaczeniu_orientacyjnym_w_terenie',
        'OIMK': 'mokradlo',
        'OISZ': 'szuwary'}

    # "P" can be store as Point or MultiPoint,
    # so it needs to be convert to single-part
    geometry_types = ["A", "L", "P"]

    for i_bdot, bdot_class in enumerate(bdot_classes):
        arcpy.AddMessage(f"{i_bdot+1} / {len(bdot_classes)}: Loop 1 - BDOT class: {bdot_class}")

        for geometry_type in geometry_types:
            arcpy.AddMessage(f"Loop 2 - geometry type: {geometry_type}")  
            class_name = bdot_class + "_" + geometry_type

            out_path = os.path.join(class_name + '_' + bdot_classes[bdot_class])
            if workspace_is_folder:
                out_path += ".shp" 

            if continue_process and arcpy.Exists(out_path):
                arcpy.AddMessage(f"{out_path} exists.")
                continue

            
            shp_to_merge = []
            for bdot_folder in bdot_folders:
                # arcpy.AddMessage(f"Loop 3 - folder:{bdot_folder}") 

                shp_files = [f for f in os.listdir(bdot_folder) if f.endswith('.shp')]
                for shp_file in shp_files:
                    shp_path = os.path.join(bdot_folder, shp_file)
                    
                    # if className in shpPath:
                    if shp_path.endswith(class_name + ".shp"):
                        arcpy.AddMessage(f"Loop 4 - File: {shp_path}")
                        shp_to_merge.append(shp_path)

            # Multipart to Singlepart for points
            if geometry_type == "P" and len(shp_to_merge) > 0:
                arcpy.AddMessage("Converting points to singlepart...")
                single_features = []
                for i_shp, shp in enumerate(shp_to_merge):
                    single_fc = f"in_memory\\single_{i_shp}"
                    single_features.append(single_fc)
                    arcpy.MultipartToSinglepart_management(shp, single_fc)

                shp_to_merge = single_features

            if len(shp_to_merge) == 1:
                if clip_area_in:
                    arcpy.AddMessage("Clipping data...")
                    arcpy.PairwiseClip_analysis(shp_to_merge[0], clip_area_in, out_path)
                else:
                    arcpy.AddMessage("Copying data...")
                    arcpy.CopyFeatures_management(shp_to_merge[0], out_path)
            elif len(shp_to_merge) > 1:
                if clip_area_in:
                    arcpy.AddMessage("In-memory clipping data...")

                    # in-memory clipping
                    clipped_features = []
                    for i_shp, shp in enumerate(shp_to_merge):
                        clipped_fc = f"in_memory\\clipped_{i_shp}"
                        clipped_features.append(clipped_fc)
                        arcpy.PairwiseClip_analysis(shp, clip_area_in, clipped_fc)
                        
                    arcpy.Merge_management(clipped_features, out_path)
                    
                    arcpy.AddMessage("Deleting in-memory datasets...")
                    for fc in clipped_features:
                        arcpy.Delete_management(fc)
                    
                else:
                    arcpy.AddMessage("Merging data...")
                    arcpy.Merge_management(shp_to_merge, out_path)
            else:
                arcpy.AddWarning("No data to process.")
                continue

            if geometry_type == "P" and len(shp_to_merge) > 0:
                arcpy.AddMessage("Deleting in-memory datasets...")
                for fc in single_features:
                    arcpy.Delete_management(fc)

            arcpy.AddMessage(f"{out_path} created.")
    return

# This is used to execute code if the file was run but not imported
if __name__ == '__main__':

    folder_in = arcpy.GetParameterAsText(0)
    if not folder_in:
        folder_in = r"<BDOT folder>"

    recursive_search = arcpy.GetParameter(1)
    if not recursive_search:
        recursive_search = True
    
    workspace_out = arcpy.GetParameterAsText(2)
    if not workspace_out:
        workspace_out = r"<output workspace>"

    spatial_ref_out = arcpy.GetParameter(3)
    if not spatial_ref_out:
        spatial_ref_out = arcpy.SpatialReference(2180)

    clip_area_in = arcpy.GetParameterAsText(4)
    if not clip_area_in:
        clip_area_in = r"<shhapefile with area of intereset>"
        
    continue_process = arcpy.GetParameter(5)
    if not continue_process:
        continue_process = False

    bdot_manager(
        folder_in,
        recursive_search,
        workspace_out,
        spatial_ref_out,
        clip_area_in,
        continue_process)
        