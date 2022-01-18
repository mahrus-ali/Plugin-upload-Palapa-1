import os
import json
import requests
from zipfile import ZipFile

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QThreadPool

from ..publish.geoserver import Geoserver
from ..publish.worker import CheckConnectionWorker

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'UploadPalapa_dialog.ui'))

class PalapaDialog(QtWidgets.QDialog, FORM_CLASS):
    
    def __init__(self, parent=None):
        """Constructor."""
        super(PalapaDialog, self).__init__(parent)
        self.setupUi(self)
        #Tab1
        self.QPushButton_test_connection.clicked.connect(self.runConnectionTest)
        self.lineEdit_username.textChanged.connect(self.connectionValuesChanged)
        self.lineEdit_password.textChanged.connect(self.connectionValuesChanged)
        self.lineEdit_url.textChanged.connect(self.connectionValuesChanged)
        #Tab2
        self.upload.setEnabled(False)
        self.upload.clicked.connect(self.uploadFile)
        self.browse_metadata.clicked.connect(self.start_browse_metadata)
        self.browse_style.clicked.connect(self.start_browse_style)
        self.url = None
        self.simpulJaringan=None
        self.grup = None
        self.user=None
        self.radioButton_StyleBrowse.toggled.connect(self.browse_style.setEnabled)
        self.radioButton_StyleBrowse.toggled.connect(self.lineEdit_style.setEnabled)

        self.threadpool = QThreadPool()
        self.check_worker = None
    
    def printError(self, ex):
        QgsMessageLog.logMessage(message=str(ex), tag='SimpleWebGis', level=Qgis.Critical)

    # Connection Test Tab1 
    def connectionValuesChanged(self):
        self.label_status.setText('')
        self.label_status.setStyleSheet("")       

    def connectionStatus(self, err_status):
        if err_status:
            self.label_status.setStyleSheet("background-color: rgb(255, 0, 0)")
            self.label_status.setText(err_status)
        else:
            self.label_status.setStyleSheet("background-color: lightgreen")
            self.label_status.setText('Terhubung')

    def runConnectionTest(self):
        # Clean label
        self.connectionValuesChanged()

        # login
        url_login=self.lineEdit_url.text()
        user=self.lineEdit_username.text()
        password=self.lineEdit_password.text()

        login_payload = {"username": user, "password": password}
        login_json = json.dumps(login_payload)
        login_api = '/api/login'
        url = url_login+login_api
        response_API = requests.post(url, data = login_json)
        responseApiJson = json.loads(response_API.text)
        if(responseApiJson['Result']):
            self.grup = responseApiJson['grup']
            self.user = responseApiJson['user']
            self.url = url_login
            responseSimpul = requests.get(self.url+'/api/sisteminfo')
            responseSimpul = json.loads(responseSimpul.text)
            self.simpulJaringan = responseSimpul['kodesimpul'].split(",")[0]
            self.upload.setEnabled(True)
        print(responseApiJson)

    #Upload Tab2
    def uploadFile(self):
        layerPath = self.exportLayer()
       
        if self.checkFileExist(layerPath['shp']) and self.checkFileExist(layerPath['dbf']) and self.checkFileExist(layerPath['shx']) and self.checkFileExist(layerPath['prj']) :
            print("file Lengkap")
            if(self.radioButton_StyleQgis.isChecked()):
                sldPath = self.exportSld()
            else:
                sldPath = self.start_browse_style()
            filesSld = {'file': open(sldPath,'rb')}
            params = {"USER":self.user,"GRUP":self.grup,"KODESIMPUL":self.simpulJaringan}
            urlSld = self.url+"/api/styles/add"
            responseAPISld = requests.post(urlSld,files=filesSld,params=params)
            zipShp = ZipFile(f"{layerPath['shp'].split('.')[0]}"+'.zip', 'w')

            # Add multiple files to the zip
            print(layerPath['shp'].split('.')[0].split('/')[-1])
            zipShp.write(f"{layerPath['shp']}",os.path.basename(layerPath['shp']))
            zipShp.write(f"{layerPath['dbf']}",os.path.basename(layerPath['dbf']))
            zipShp.write(f"{layerPath['shx']}",os.path.basename(layerPath['shx']))
            zipShp.write(f"{layerPath['prj']}",os.path.basename(layerPath['prj']))
            # close the Zip File
            zipShp.close()
            files = {'file': open(f"{layerPath['shp'].split('.')[0]}"+'.zip','rb')}
            print(files)
            
            urlUpload = self.url+"/api/upload"
            responseAPIZip = requests.post(urlUpload,files=files,params=params)
            dataPublish = json.loads(responseAPIZip.text)
            print(dataPublish,"publish")
            self.publish(dataPublish['SEPSG'],dataPublish['LID'],dataPublish['TIPE'],dataPublish['ID'])

            if(self.radioButton_StyleQgis.isChecked()):
                filesSld['file'].close()
                os.remove(sldPath)
            files['file'].close() 
            os.remove(layerPath['shp'].split('.')[0]+'.zip')

            # filesShp = {'file': open(layerPath['shp'],'rb')}
            # filesDbf = {'file': open(layerPath['dbf'],'rb')}
            # filesShx = {'file': open(layerPath['shx'],'rb')}
            # filesPrj = {'file': open(layerPath['prj'],'rb')}

            # urlShp = self.url+"/api/uploadshp"
            # urlDbf = self.url+"/api/uploaddbf"
            # urlShx = self.url+"/api/uploadshx"
            # urlPrj = self.url+"/api/uploadprj"
      
            # print(urlShp)

            # responseAPIShp = requests.post(urlShp,files=filesShp,params=params)
            # responseAPIDbf = requests.post(urlDbf,files=filesDbf,params=params)
            # responseAPIShx = requests.post(urlShx,files=filesShx,params=params)
            # responseAPIPrj = requests.post(urlPrj,files=filesPrj,params=params)
       
            # print(responseAPISld.text)
            # print(responseAPIPrj.text)
            # dataPublish = json.loads(responseAPIPrj.text)
            # self.publish(dataPublish['SEPSG'],dataPublish['LID'],dataPublish['TIPE'],dataPublish['ID'])
   
        else :
            print("file Tidak Lengkap")
    
    def publish(self,kodeEpsg,Lid,Tipe,id):
        url = self.url + "/api/publish"
        dataPublish = {"pubdata":{"LID": Lid, "TIPE": Tipe,"ID":id,"ABS":"","SEPSG":kodeEpsg,"USER":self.user,"GRUP":self.grup}}
        dataPublish = json.dumps(dataPublish)
        respond = requests.post(url,data=f"dataPublish={dataPublish}")
        print(respond.text)
      
    def exportLayer(self):
        layerName = self.select_layer.currentText()
        layer = QgsProject().instance().mapLayersByName(layerName)[0]
        source = layer.source()
        source = source.split("|")
        try:
            shp = source[0]
            prj = source[0].replace(".shp", ".prj")
            dbf = source[0].replace(".shp", ".dbf")
            shx = source[0].replace(".shp", ".shx")
            sourceFile = json.loads('{"shp":"%s","prj":"%s","dbf":"%s","shx":"%s","nama":"%s"}'%(shp,prj,dbf,shx,layerName))
            return sourceFile
        except:
            return print("File Tidak ditemukan")
   
    def checkFileExist(self,filePath):
        fileExist = True
        if os.path.isfile(filePath):
            print ("File exist")
            fileExist = True
        else:
            print ("File not exist")
            fileExist = False
        return fileExist

    def exportSld(self):
        layerName = self.select_layer.currentText()
        layer = QgsProject().instance().mapLayersByName(layerName)[0]
        path = f'D:/{layerName}.sld'
        layer.saveSldStyle(path)
        return path
    

    def start_browse_metadata(self):
        filename1, _ = QFileDialog.getOpenFileName()
        print(filename1)
        self.lineEdit_metadata.setText(filename1)
        return filename1

    def start_browse_style(self):
        filename2, _ = QFileDialog.getOpenFileName()
        print(filename2)
        self.lineEdit_style.setText(filename2)
        return filename2

    #upload Metadata
    def uploadMetadata(self) :
        metadataPath = self.start_browse_metadata()
        filesMeta = {'file': open(metadataPath,'rb')}
        params = {"USER":self.user,"GRUP":self.grup,"KODESIMPUL":self.simpulJaringan}
        urlMeta = self.url+"/api/meta/links"
        responseAPIMeta = requests.post(urlMeta,files=filesMeta,params=params)
        print (responseAPIMeta.text)
        
        #if self.checkMetadataExist(metadataPath['xml']) :
            #print("metadata lengkap")
    
  


