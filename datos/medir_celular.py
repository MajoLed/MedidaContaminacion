#!/usr/bin/env python2
# -*- coding: utf-8 -*-
##################################################
# GNU Radio Python Flow Graph
# Title: final
# Generated: Tue May 15 10:15:25 2018
##################################################

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print "Warning: failed to XInitThreads()"

from PyQt4 import Qt
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio import qtgui
from gnuradio import uhd
from gnuradio.eng_option import eng_option
from gnuradio.filter import firdes
from gnuradio.qtgui import Range, RangeWidget
from optparse import OptionParser
import sip
import sys
import time
import biblioteca
import numpy
import csv
import pynmea2
import gmplot
import matplotlib.pyplot as pt
from gnuradio import qtgui


class ejemplo_1_m(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "final")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("final")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "ejemplo_1_m")
        self.restoreGeometry(self.settings.value("geometry").toByteArray())

        ##################################################
        # Variables
        ##################################################
        self.temperatura = temperatura = '0'
        self.samp_rate = samp_rate = 20E6
        self.nombrearchivo = nombrearchivo = ''
        self.longitud = longitud = '0'
        self.latitud = latitud = '0'
        self.fc = fc = 850e6
        self.botonmedir = botonmedir = 0
        self.mibloque=biblioteca.sampler()

        ##################################################
        # Blocks
        ##################################################
        self._fc_range = Range(850e6, 960e6, 4e6, 850e6, 2000)
        self._fc_win = RangeWidget(self._fc_range, self.set_fc, 'Frecuencia central', "counter_slider", float)
        self.top_layout.addWidget(self._fc_win)
        self.uhd_usrp_source_0 = uhd.usrp_source(
        	",".join(("", "")),
        	uhd.stream_args(
        		cpu_format="fc32",
        		channels=range(1),
        	),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_center_freq(fc, 0)
        self.uhd_usrp_source_0.set_gain(40, 0)
        self.uhd_usrp_source_0.set_antenna('RX2', 0)
        self._temperatura_tool_bar = Qt.QToolBar(self)

        if None:
          self._temperatura_formatter = None
        else:
          self._temperatura_formatter = lambda x: str(x)

        self._temperatura_tool_bar.addWidget(Qt.QLabel("temperatura"+": "))
        self._temperatura_label = Qt.QLabel(str(self._temperatura_formatter(self.temperatura)))
        self._temperatura_tool_bar.addWidget(self._temperatura_label)
        self.top_grid_layout.addWidget(self._temperatura_tool_bar, 1,0)

        self.qtgui_sink_x_0 = qtgui.sink_c(
        	1024, #fftsize
        	firdes.WIN_BLACKMAN_hARRIS, #wintype
        	fc, #fc
        	samp_rate, #bw
        	"", #name
        	True, #plotfreq
        	True, #plotwaterfall
        	True, #plottime
        	True, #plotconst
        )
        self.qtgui_sink_x_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_win = sip.wrapinstance(self.qtgui_sink_x_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_sink_x_0_win, 0,0)

        self.qtgui_sink_x_0.enable_rf_freq(False)



        self._nombrearchivo_tool_bar = Qt.QToolBar(self)
        self._nombrearchivo_tool_bar.addWidget(Qt.QLabel('NOMBRE ARCHIVO:'+": "))
        self._nombrearchivo_line_edit = Qt.QLineEdit(str(self.nombrearchivo))
        self._nombrearchivo_tool_bar.addWidget(self._nombrearchivo_line_edit)
        self._nombrearchivo_line_edit.returnPressed.connect(
        	lambda: self.set_nombrearchivo(str(str(self._nombrearchivo_line_edit.text().toAscii()))))
        self.top_grid_layout.addWidget(self._nombrearchivo_tool_bar, 4,0)
        self._longitud_tool_bar = Qt.QToolBar(self)

        if None:
          self._longitud_formatter = None
        else:
          self._longitud_formatter = lambda x: str(x)

        self._longitud_tool_bar.addWidget(Qt.QLabel("longitud"+": "))
        self._longitud_label = Qt.QLabel(str(self._longitud_formatter(self.longitud)))
        self._longitud_tool_bar.addWidget(self._longitud_label)
        self.top_grid_layout.addWidget(self._longitud_tool_bar, 2,0)

        self._latitud_tool_bar = Qt.QToolBar(self)

        if None:
          self._latitud_formatter = None
        else:
          self._latitud_formatter = lambda x: str(x)

        self._latitud_tool_bar.addWidget(Qt.QLabel("latitud"+": "))
        self._latitud_label = Qt.QLabel(str(self._latitud_formatter(self.latitud)))
        self._latitud_tool_bar.addWidget(self._latitud_label)
        self.top_grid_layout.addWidget(self._latitud_tool_bar, 3,0)

        _botonmedir_push_button = Qt.QPushButton('MEDIR')
        self._botonmedir_choices = {'Pressed': 1, 'Released': 0}
        _botonmedir_push_button.pressed.connect(lambda: self.set_botonmedir(self._botonmedir_choices['Pressed']))
        _botonmedir_push_button.pressed.connect(lambda: self.set_botonmedir(self.medida()))
        _botonmedir_push_button.released.connect(lambda: self.set_botonmedir(self._botonmedir_choices['Released']))
        self.top_grid_layout.addWidget(_botonmedir_push_button, 5,0)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.uhd_usrp_source_0, 0),  (self.mibloque, 0))
        self.connect((self.mibloque, 0), (self.qtgui_sink_x_0, 0))

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "ejemplo_1_m")
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def get_temperatura(self):
        return self.temperatura

    def set_temperatura(self, temperatura):
        self.temperatura = temperatura
        Qt.QMetaObject.invokeMethod(self._temperatura_label, "setText", Qt.Q_ARG("QString", self.temperatura))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.qtgui_sink_x_0.set_frequency_range(self.fc, self.samp_rate)

    def get_nombrearchivo(self):
        return self.nombrearchivo

    def set_nombrearchivo(self, nombrearchivo):
        self.nombrearchivo = nombrearchivo
        Qt.QMetaObject.invokeMethod(self._nombrearchivo_line_edit, "setText", Qt.Q_ARG("QString", str(self.nombrearchivo)))

    def get_longitud(self):
        return self.longitud

    def set_longitud(self, longitud):
        self.longitud = longitud
        Qt.QMetaObject.invokeMethod(self._longitud_label, "setText", Qt.Q_ARG("QString", self.longitud))

    def get_latitud(self):
        return self.latitud

    def set_latitud(self, latitud):
        self.latitud = latitud
        Qt.QMetaObject.invokeMethod(self._latitud_label, "setText", Qt.Q_ARG("QString", self.latitud))

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.uhd_usrp_source_0.set_center_freq(self.fc, 0)
        self.qtgui_sink_x_0.set_frequency_range(self.fc, self.samp_rate)

    def get_botonmedir(self):
        return self.botonmedir

    def set_botonmedir(self, botonmedir):
        self.botonmedir = botonmedir


    def medida(self):

        print(str(self.get_nombrearchivo()))
        num_medidas = 100

        potencia= [-1000]*1024
        vector= []

        for contador in range(0,num_medidas):
             vector= self.mibloque.muestras
             espectro= 20*numpy.log10(numpy.abs(numpy.fft.fftshift((numpy.fft.fft(vector,n=1024))/len(vector))))

             for i in range(0,1024):
                if potencia[i]<espectro[i]:
                   potencia[i]=espectro[i]





        #pt.plot(potencia)
        #pt.show()
        readgga=str(self.uhd_usrp_source_0.get_mboard_sensor("gps_gpgga"))
        temperatura=str(self.uhd_usrp_source_0.get_sensor("temp"))
        print temperatura
        b=readgga.split()[1]



        reader= pynmea2.parse(b)



        self.set_latitud(str(reader.latitude))
        self.set_longitud(str(reader.longitude))
        #self.set_altitud(str(reader.altitude))
        #self.set_error(str(reader.horizontal_dil))

        #gmap = gmplot.GoogleMapPlotter(reader.latitude, reader.longitude, 20)
        #gmap.marker(reader.latitude, reader.longitude, 'cornflowerblue')
        #gmap.draw("my_map.html")
        potencia.append(eval(temperatura.split()[1]))
        potencia.append(eval(str(reader.longitude)))
        potencia.append(eval(str(reader.latitude)))
        potencia.append(eval(str(reader.altitude)))
        potencia.append(eval(str(reader.horizontal_dil)))



        print potencia
        with open(str(self.get_nombrearchivo()), "wb") as fo:
             writer1 = csv.writer(fo)
             writer1.writerows([potencia])
        fo.close()




def main(top_block_cls=ejemplo_1_m, options=None):

    from distutils.version import StrictVersion
    print Qt.qVersion()
    if StrictVersion(Qt.qVersion()) >= StrictVersion("4.5.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'opengl')
        print "coloca en raster"
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()
    tb.start()
    tb.show()

    def quitting():
        tb.stop()
        tb.wait()
    qapp.connect(qapp, Qt.SIGNAL("aboutToQuit()"), quitting)
    qapp.exec_()


if __name__ == '__main__':
    main()
