# -*- coding: UTF-8 -*-
from osgeo import gdal
from qgis.core import *
import os
import shutil
import sys

#---------------------------------------
#----       Variables globales      ----
#---------------------------------------

dBase = 'E:/IPCC/'                                      # unidad de disco y directorio base
dGlob = 'Future/'                                       # subdirectorio de los archivos GeoTiff
dOutput = 'output/'                                     # subdirectorio de salida de los recortes
tmpFolder = 'C:/Windows/Temp/'                          # directorio para los archivos temporales

dirShapes = 'E:/IPCC/shapes/'                           # directorio de los poligonos para los recortes
rcSHP = os.path.join(dirShapes, 'municipio-puebla-limite.shp')     # poligono limite territorial
rcSHP_ext = os.path.join(dirShapes, 'puebla-extension.shp')    # poligono extension del limite territorial

sufijo = '_future'                                      # sufijo para el archivo de salida

multiple = 750                                          # multiplo para remuestrear GeoTiff
roundTo = 2                                             # digitos decimales (>=1) para las variables

#---------------------------------------
#--      Parametros (no modificar)    --
#---------------------------------------

variables  = ['Prec', 'Tmax', 'Tmed', 'Tmin']           # variables abreviadas
horizontes = ['2021-2040', '2041-2060', '2081-2100']    # horizontes
escenarios = ['ssp245', 'ssp370', 'ssp585']             # escenarios

ipcc_vars = ['(PR)', '(TX)', '(T)', '(TN)']             # variables Ipcc
ipcc_ssps = ['SSP2-4.5', 'SSP3-7.0', 'SSP5-8.5']        # escenario Ipcc
theMonths = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                'September', 'October', 'November', 'December']

#---------------------------------------
#----           Subrutinas          ----
#---------------------------------------

def recortaNombreArchivo ( theFile ):
    the_file = theFile[8:-5].lower() + theFile[-5:]
    nombreAjustado = theFile[:5].lower() + '_ippc' + sufijo
    
    for i in range(len(ipcc_vars)):
        if the_file.find(ipcc_vars[i].lower())!=-1:
            nombreAjustado = nombreAjustado + '_' + variables[i].lower()
            break
    for i in range(len(ipcc_ssps)):
        if the_file.find(ipcc_ssps[i].lower())!=-1:
            nombreAjustado = nombreAjustado + '_' + escenarios[i]
            break
    for anio in horizontes:
        if the_file.find(anio)!=-1:
            nombreAjustado = nombreAjustado + '_' + anio[2:4] + '-' + anio[-2:]
            break
    for i in range(len(theMonths)):
        if the_file.find(theMonths[i].lower())!=-1:
            nombreAjustado = nombreAjustado + '_' + str(i+1).zfill(2)
            break
    return nombreAjustado + '.tiff'

def getBasicInfoRaster(theRasterFile):
    theRaster = gdal.Open( theRasterFile )
    dataType = theRaster.GetRasterBand(1).DataType
    noDataVal = theRaster.GetRasterBand(1).GetNoDataValue()
    gt = theRaster.GetGeoTransform()
    theRaster = None
    return {'dataType': dataType, 'noDataVal': noDataVal, 'PixelSizeX': abs(gt[1]), 'PixelSizeY': abs(gt[5])}

def saveStatisticsToCSV(layer, file_name, path_s):
    file_s = file_name[0:-7]
    the_file = file_s + '.txt'
    
    if not os.path.isfile( os.path.join(path_s, the_file) ):
        with open( os.path.join(path_s, the_file), 'w') as file:
            content = 'month,'
            for c in layer.fields().names(): content += c + ','
            file.write( content[:-1] )
    
    content = ''
    with open( os.path.join(path_s, the_file), 'a') as file:
        content = file_name[-6:-4] + ','
        for f in layer.fields().names(): content += str( round(layer.getFeature(0)[f], roundTo) ) + ','
        file.write( '\n' + content[:-1] )
    
def transalateTiff( inFile, outFile, listBand ):
    basicInfo = getBasicInfoRaster( inFile )
    opts = gdal.TranslateOptions(format = "GTiff", outputType = basicInfo['dataType'], bandList = listBand,
                maskBand = None, noData = basicInfo['noDataVal'], stats = True, resampleAlg = 'nearest',
                xRes = basicInfo['PixelSizeX'] / multiple, yRes = basicInfo['PixelSizeY'] / multiple )
    oBand = gdal.Translate( destName = outFile, srcDS = inFile, options = opts )
    oBand = None

def warpTiff( outFile, inFile, the_layer ):
    basicInfo = getBasicInfoRaster( inFile )
    optns = gdal.WarpOptions( cutlineDSName = the_layer, outputType = basicInfo['dataType'],
                workingType = basicInfo['dataType'], srcNodata = basicInfo['noDataVal'],
                dstNodata = basicInfo['noDataVal'], cropToCutline = True )
    oBand = gdal.Warp( srcDSOrSrcDSTab = inFile, destNameOrDestDS = outFile, options = optns )
    oBand = None

def deleteAttributesFields(layer):
    count = layer.fields().count()
    layer.dataProvider().deleteAttributes( [i for i in range(0, count)] )
    layer.updateFields()


#---------------------------------------
#----              MAIN             ----
#---------------------------------------

QgsProject.instance().removeAllMapLayers()
limitLayer = iface.addVectorLayer( rcSHP, '', 'ogr')

if not os.path.isdir( dBase ) or not os.path.isdir( os.path.join(dBase, dGlob) ) :
    print ("El directorio base no existe '%s'. No se puede continuar. " % dGlob)
    sys.exit(1)

oRect = os.path.join(dBase, dGlob, dOutput)                     # ruta base del directorio de salida
if not os.path.isdir( oRect ): os.mkdir( oRect )                # si no existe, crear el directorio

n_files = 0
for file in [ file for file in os.listdir( os.path.join(dBase, dGlob) ) if file[-5:]=='.tiff' ]:
    
    # recortar capa por la extesion (warp)
    warpTiff( os.path.join(tmpFolder, 'tmp1.tiff'), os.path.join(dBase, dGlob, file), rcSHP_ext )
    
    newFile = recortaNombreArchivo( file )
    print ("Processing => " + newFile)
    
    # remuestrear archivo (resample)
    transalateTiff( os.path.join(tmpFolder, 'tmp1.tiff'), os.path.join(tmpFolder, 'tmp2.tiff'), [1] )
    
    # cargar capa al proyecto
    src_ds = gdal.Open( os.path.join(tmpFolder, 'tmp2.tiff') )
    rlayer = QgsRasterLayer( os.path.join(tmpFolder, 'tmp2.tiff'), newFile[:-5] )
    QgsProject.instance().addMapLayer(rlayer, True)
    
    # calcular estadisticas de zona (zonal statistics), todas las variables
    zoneStats = QgsZonalStatistics( limitLayer, rlayer, "", 1, QgsZonalStatistics.All )
    zoneStats.calculateStatistics( None )
    saveStatisticsToCSV( limitLayer, newFile, oRect )
    deleteAttributesFields( limitLayer )
    
    # recortar capa por el area de interes (warp)
    warpTiff( os.path.join(oRect, newFile), os.path.join(tmpFolder, 'tmp2.tiff'), rcSHP )
    
    # eliminar capa cargada al proyecto
    QgsProject.instance().removeMapLayer( rlayer.id() )
    src_ds = None
    
    n_files = n_files + 1
    
# limpiar el proyecto
QgsProject.instance().removeAllMapLayers()
print("\n{} archivos procesados".format(n_files))