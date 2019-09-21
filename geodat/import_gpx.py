# -*- coding: utf-8 -*-
# -------------------------------------------------
# -- gpx importer
# --
# -- microelly 2016 v 0.0
# --
# -- GNU Lesser General Public License (LGPL)
# -------------------------------------------------
'''gpx path importer'''

# \cond
import pivy
from pivy import coin
import sys
import FreeCAD
import FreeCADGui
import Part
import Draft
from geodat.transversmercator import TransverseMercator
from geodat.xmltodict import parse
from geodat.say import *
import time
import json
import os

import geodat.inventortools

# test-data from https://en.wikipedia.org/wiki/GPS_Exchange_Format

trackstring = '''
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" creator="Oregon 400t" version="1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www.garmin.com/xmlschemas/GpxExtensionsv3.xsd http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd">
  <metadata>
    <link href="http://www.garmin.com">
      <text>Garmin International</text>
    </link>
    <time>2009-10-17T22:58:43Z</time>
  </metadata>
  <trk>
    <name>Example GPX Document</name>
    <trkseg>
      <trkpt lat="47.644548" lon="-122.326897">
        <ele>4.46</ele>
        <time>2009-10-17T18:37:26Z</time>
      </trkpt>
      <trkpt lat="47.644549" lon="-122.326898">
        <ele>4.94</ele>
        <time>2009-10-17T18:37:31Z</time>
      </trkpt>
      <trkpt lat="47.644550" lon="-122.326898">
        <ele>6.87</ele>
        <time>2009-10-17T18:37:34Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
'''


# https://de.wikipedia.org/wiki/GPS_Exchange_Format
'''
<ele> xsd:decimal </ele>                     <!-- Höhe in m -->
<time> xsd:dateTime </time>                  <!-- Datum und Zeit (UTC/Zulu) in ISO 8601 Format: yyyy-mm-ddThh:mm:ssZ -->
<magvar> degreesType </magvar>               <!-- Deklination / magnetische Missweisung vor Ort in Grad -->
<geoidheight> xsd:decimal </geoidheight>     <!-- Höhe bezogen auf Geoid -->
<name> xsd:string </name>                    <!-- Eigenname des Elements -->
<cmt> xsd:string </cmt>                      <!-- Kommentar -->
<desc> xsd:string </desc>                    <!-- Elementbeschreibung -->
<src> xsd:string </src>                      <!-- Datenquelle/Ursprung -->
<link> linkType </link>                      <!-- Link zu weiterführenden Infos -->
<sym> xsd:string </sym>                      <!-- Darstellungssymbol -->
<type> xsd:string </type>                    <!-- Klassifikation -->
<fix> fixType </fix>                         <!-- Art der Positionsfeststellung: none, 2d, 3d, dgps, pps -->
<sat> xsd:nonNegativeInteger </sat>          <!-- Anzahl der zur Positionsberechnung herangezogenen Satelliten -->
<hdop> xsd:decimal </hdop>                   <!-- HDOP: Horizontale Streuung der Positionsangabe -->
<vdop> xsd:decimal </vdop>                   <!-- VDOP: Vertikale Streuung der Positionsangabe -->
<pdop> xsd:decimal </pdop>                   <!-- PDOP: Streuung der Positionsangabe -->
<ageofdgpsdata> xsd:decimal </ageofdgpsdata> <!-- Sekunden zwischen letztem DGPS-Empfang und Positionsberechnung -->
<dgpsid> dgpsStationType:integer </dgpsid>   <!-- ID der verwendeten DGPS Station -->
<extensions> extensionsType </extensions>    <!-- GPX Erweiterung -->
'''


if sys.version_info[0] != 2:
    from importlib import reload


App = FreeCAD
Gui = FreeCADGui

debug = False


global sd

# \endcond
import re


def import_gpx(filename, orig, hi):
    '''import a gpx trackfile'''

    global sd
    f = open(filename, "r")
    c1 = f.read()
    content = re.sub('^\<\?[^\>]+\?\>', '', c1)
    print(content)

    tm = TransverseMercator()

    # outdoor inn ...
    tm.lat, tm.lon = 50.3736049, 11.191643

    if orig != 'auto':
        yy = orig.split(',')
        origin = (float(yy[0]), float(yy[1]))
        tm.lat = origin[0]
        tm.lon = origin[1]

    sd = parse(content)

    if debug:
        print(json.dumps(sd, indent=4))

    points = []
    points2 = []
    points0 = []
    px = []
    py = []
    pz = []
    pt = []

    startx = None
    starty = None
    starth = None
    FreeCAD.sd = sd
    seg = sd['gpx']['trk']['trkseg']

    try:
        seg['trkpt']
        ss = seg
        seg = [ss]

    except:
        pass

    lats = []
    lons = []

    for s in seg:
        trkpts = s['trkpt']

        for n in trkpts:
            lats.append(float(n['@lat']))
            lons.append(float(n['@lon']))

    print(min(lats), max(lats))
    print(min(lons), max(lons))
    print((max(lats)+min(lats))/2, (max(lons)+min(lons))/2)
    print((max(lats)-min(lats))/2, (max(lons)-min(lons))/2)

    if orig == 'auto':
        tm.lat, tm.lon = (max(lats)+min(lats))/2, (max(lons)+min(lons))/2
        print("origin:")
        print(tm.lat, tm.lon)
        print("----------")

    for s in seg:
        trkpts = s['trkpt']
        n = trkpts[0]
        center = tm.fromGeographic(tm.lat, tm.lon)

        # map all points to xy-plane
        for n in trkpts:
            lats.append(float(n['@lat']))
            lons.append(float(n['@lon']))
            ll = tm.fromGeographic(float(n['@lat']), float(n['@lon']))
            h = n['ele']
            tim = n['time']
            t2 = re.sub('^.*T', '', tim)
            t3 = re.sub('Z', '', t2)
            t4 = t3.split(':')
            timx = int(t4[0])*3600+int(t4[1])*60+int(t4[2])
            pt.append(timx)

            if starth == None:
                starth = float(h)
                starth = 0

            points.append(FreeCAD.Vector(ll[0]-center[0], ll[1]-center[1], 1000*(float(h)-starth)))
            points.append(FreeCAD.Vector(ll[0]-center[0], ll[1]-center[1], 0))
            points.append(FreeCAD.Vector(ll[0]-center[0], ll[1]-center[1], 1000*(float(h)-starth)))
            points2.append(FreeCAD.Vector(ll[0]-center[0], ll[1]-center[1], 1000*(float(h)-starth)+20000))
            points0.append(FreeCAD.Vector(ll[0]-center[0], ll[1]-center[1], 0))
            px.append(ll[0]-center[0])
            py.append(ll[1]-center[1])
            pz.append(1000*(float(h)-starth))

	Draft.makeWire(points0)

	Draft.makeWire(points)

	po = App.ActiveDocument.ActiveObject
	po.ViewObject.LineColor = (1.0, 0.0, 0.0)
	po.MakeFace = False

	po.Placement.Base.z = float(hi) * 1000
	po.Label = "My Track"

	Draft.makeWire(points2)

	po2 = App.ActiveDocument.ActiveObject
	po2.ViewObject.LineColor = (0.0, 0.0, 1.0)
	po2.ViewObject.PointSize = 5
	po2.ViewObject.PointColor = (0.0, 1.0, 1.0)

	po2.Placement.Base.z = float(hi)*1000
	po2.Label = "Track + 20m"

	App.activeDocument().recompute()
	Gui.SendMsgToActiveView("ViewFit")


    return str(tm.lat)+','+str(tm.lon)



s6 = '''
MainWindow:
	VerticalLayout:
		id:'main'

		QtGui.QLabel:
			setText:"***   I M P O R T    GPX  T R A C K    ***"
		QtGui.QLabel:

		QtGui.QLabel:
			setText:"Track input filename"

		QtGui.QLineEdit:
			setText:"UserAppData/Mod/geodat/testdata/neufang.gpx"
			id: 'bl'

		QtGui.QPushButton:
			setText: "Get GPX File Name"
			clicked.connect: app.getfn

		QtGui.QLabel:
			setText:"Origin (lat,lon) "

		QtGui.QLineEdit:
#			setText:"50.3736049,11.191643"
			setText:"auto"
			id: 'orig'

		QtGui.QLabel:
			setText:"relative Height of the Startpoint"

		QtGui.QLineEdit:
#			setText:"-197.55"
			setText:"0"
			id: 'h'

		QtGui.QRadioButton:
			setText: "Generate Data Nodes "
#			clicked.connect: app.run_co2


		QtGui.QPushButton:
			setText: "Run values"
			clicked.connect: app.run

'''


# Gui backend
class MyApp(object):
    """
	The  execution layer of import_gpx
	"""

    def run(self):
        """
		Calls import_gpx
		"""

        filename = self.root.ids['bl'].text()
        if filename.startswith('UserAppData'):
            filename = filename.replace('UserAppData', FreeCAD.ConfigGet("UserAppData"))

        try:
            rc = import_gpx(
                filename,
                self.root.ids['orig'].text(),
                self.root.ids['h'].text(),
            )
            self.root.ids['orig'].setText(rc),
        
        except:
            sayexc()

    def getfn(self):
        """
		Get the filename of the track
		"""

        fileName = QtGui.QFileDialog.getOpenFileName(None, u"Open File", u"/tmp/")
        print(fileName)
        s = self.root.ids['bl']
        s.setText(fileName[0])


# the dialog to import the file
def mydialog():
    """
	The dialog to import the file
	"""

    app = MyApp()

    import geodat
    import geodat.miki as miki
    reload(miki)

    miki = miki.Miki()
    miki.app = app
    app.root = miki

    miki.parse2(s6)
    miki.run(s6)
    return miki


# tst open and hide dialog
def runtest():
    m = mydialog()
    m.objects[0].hide()


def importGPXTrack():
    m = mydialog()


if __name__ == '__main__':
    runtest()
