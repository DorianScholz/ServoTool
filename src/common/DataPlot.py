#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
import sys, math

from PyQt4.QtGui import QPen, QTextEdit
from PyQt4.QtCore import QEvent, QPointF, QTimer, Qt, pyqtSignal as Signal, pyqtSlot as Slot

try:
    import PyQt4.Qwt5 as Qwt
    from PyQt4.Qwt5.anynumpy import arange, zeros, concatenate

except Exception, e:

    # create dummy class
    class DataPlot(QTextEdit):
        def __init__(self, *args):
            QTextEdit.__init__(self, *args)
            msg = 'WARNING: could not import PyQwt5\nPlease install "python-qwt5-qt4" to enable data plotting.\n\nError message:\n' + str(e)
            print msg
            self.setText(msg)
            self.setReadOnly(True)

        def setRedrawInterval(self, interval):
            pass

        def addCurve(self, curveId, curveName):
            pass

        def hasCurve(self, curveId):
            return False

        def removeCurve(self, curveId):
            pass

        def updateValue(self, curveId, value):
            pass

        @Slot(bool)
        def toggleOscilloscopeMode(self, enabled):
            pass

        def removeAllCurves(self):
            pass

        @Slot(bool)
        def togglePause(self, enabled):
            pass

else:

    # create real DataPlot class
    class DataPlot(Qwt.QwtPlot):
        mouseCoordinatesChanged = Signal(QPointF)
        colors = [Qt.red, Qt.blue, Qt.magenta, Qt.cyan, Qt.green]
        dataNumValuesSaved = 1000
        dataNumValuesPloted = 1000

        def __init__(self, *args):
            super(DataPlot, self).__init__(*args)
            self.setCanvasBackground(Qt.white)
            self.insertLegend(Qwt.QwtLegend(), Qwt.QwtPlot.BottomLegend)

            self.curves = {}
            self.pauseFlag = False
            self.dataOffsetX = 0
            self.canvasOffsetX = 0
            self.canvasOffsetY = 0
            self.lastCanvasX = 0
            self.lastCanvasY = 0
            self.pressedCanvasY = 0
            self.redrawOnEachUpdate = False
            self.redrawOnFullUpdate = True
            self.redrawTimerInterval = None
            self.redrawManually = False
            self.oscilloscopeNextDataPosition = 0
            self.oscilloscopeMode = False
            self.lastClickCoordinates = None

            markerAxisY = Qwt.QwtPlotMarker()
            markerAxisY.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
            markerAxisY.setLineStyle(Qwt.QwtPlotMarker.HLine)
            markerAxisY.setYValue(0.0)
            markerAxisY.attach(self)

            #self.setAxisTitle(Qwt.QwtPlot.xBottom, "Time")
            #self.setAxisTitle(Qwt.QwtPlot.yLeft, "Value")


            self.picker = Qwt.QwtPlotPicker(
                Qwt.QwtPlot.xBottom, Qwt.QwtPlot.yLeft, Qwt.QwtPicker.PolygonSelection,
                Qwt.QwtPlotPicker.PolygonRubberBand, Qwt.QwtPicker.AlwaysOn, self.canvas()
            )
            self.picker.setRubberBandPen(QPen(self.colors[-1]))
            self.picker.setTrackerPen(QPen(self.colors[-1]))

            # Initialize data
            self.timeAxis = arange(self.dataNumValuesPloted)
            self.canvasDisplayHeight = 1000
            self.canvasDisplayWidth = self.canvas().width()
            self.dataOffsetX = self.dataNumValuesSaved - len(self.timeAxis)
            self.redraw()
            self.moveCanvas(0, 0)
            self.canvas().setMouseTracking(True)
            self.canvas().installEventFilter(self)

            # init and start redraw timer
            self.timerRedraw = QTimer(self)
            self.timerRedraw.timeout.connect(self.redraw)
            if self.redrawTimerInterval:
                self.timerRedraw.start(self.redrawTimerInterval)

        def eventFilter(self, _, event):
            if event.type() == QEvent.MouseButtonRelease:
                x = self.invTransform(Qwt.QwtPlot.xBottom, event.pos().x())
                y = self.invTransform(Qwt.QwtPlot.yLeft, event.pos().y())
                self.lastClickCoordinates = QPointF(x, y)
            elif event.type() == QEvent.MouseMove:
                x = self.invTransform(Qwt.QwtPlot.xBottom, event.pos().x())
                y = self.invTransform(Qwt.QwtPlot.yLeft, event.pos().y())
                coords = QPointF(x, y)
                if self.picker.isActive() and self.lastClickCoordinates is not None:
                    toolTip = 'origin x: %.5f, y: %.5f' % (self.lastClickCoordinates.x(), self.lastClickCoordinates.y())
                    delta = coords - self.lastClickCoordinates
                    toolTip += '\ndelta x: %.5f, y: %.5f\nlength: %.5f' % (delta.x(), delta.y(), math.sqrt(delta.x() ** 2 + delta.y() ** 2))
                else:
                    toolTip = 'buttons\nleft: measure\nmiddle: move\nright: zoom x/y\nwheel: zoom y'
                self.setToolTip(toolTip)
                self.mouseCoordinatesChanged.emit(coords)
            return False

        def setRedrawInterval(self, interval):
            self.redrawTimerInterval = interval
            if self.redrawTimerInterval:
                self.redrawOnEachUpdate = False
                self.redrawOnFullUpdate = False
                self.timerRedraw.start(self.redrawTimerInterval)

        def resizeEvent(self, event):
            super(DataPlot, self).resizeEvent(event)
            self.rescale()

        def getCurves(self):
            return self.curves

        def addCurve(self, curveId, curveName):
            curveId = str(curveId)
            if self.curves.get(curveId):
                return
            curveObject = Qwt.QwtPlotCurve(curveName)
            curveObject.attach(self)
            curveObject.setPen(QPen(self.colors[len(self.curves.keys()) % len(self.colors)]))
            self.curves[curveId] = {
                'name': curveName,
                'data': zeros(self.dataNumValuesSaved),
                'object': curveObject,
            }

        def removeCurve(self, curveId):
            curveId = str(curveId)
            if curveId in self.curves:
                self.curves[curveId]['object'].hide()
                self.curves[curveId]['object'].attach(None)
                del self.curves[curveId]['object']
                del self.curves[curveId]

        def removeAllCurves(self):
            for curveId in self.curves.keys():
                self.removeCurve(curveId)
            self.clear()

        @Slot(str, float)
        def updateValue(self, curveId, value):
            curveId = str(curveId)
            # update data plot
            if (not self.pauseFlag) and curveId in self.curves:
                if self.oscilloscopeMode:
                    self.curves[curveId]['data'][self.oscilloscopeNextDataPosition] = float(value)
                    # only advance the oscilloscopeNextDataPosition for the first curve in the dict
                    if self.curves.keys()[0] == curveId:
                        self.oscilloscopeNextDataPosition = (self.oscilloscopeNextDataPosition + 1) % len(self.timeAxis)
                else:
                    self.curves[curveId]['data'] = concatenate((self.curves[curveId]['data'][1:], self.curves[curveId]['data'][:1]), 1)
                    self.curves[curveId]['data'][-1] = float(value)

                if not self.redrawManually:
                    if self.redrawOnEachUpdate or (self.redrawOnFullUpdate and self.curves.keys()[0] == curveId):
                        self.redraw()

        @Slot(bool)
        def togglePause(self, enabled):
            self.pauseFlag = enabled

        @Slot(bool)
        def toggleOscilloscopeMode(self, enabled):
            self.oscilloscopeMode = enabled

        def hasCurve(self, curveId):
            curveId = str(curveId)
            return curveId in self.curves

        def redraw(self):
            for curveId in self.curves.keys():
                self.curves[curveId]['object'].setData(self.timeAxis, self.curves[curveId]['data'][self.dataOffsetX : self.dataOffsetX + len(self.timeAxis)])
                #self.curves[curveId]['object'].setStyle(Qwt.QwtPlotCurve.CurveStyle(3))
            self.replot()

        def rescale(self):
            yNumTicks = self.height() / 40
            yLowerLimit = self.canvasOffsetY - (self.canvasDisplayHeight / 2)
            yUpperLimit = self.canvasOffsetY + (self.canvasDisplayHeight / 2)

            # calculate a fitting step size for nice, round tick labels, depending on the displayed value area
            yDelta = yUpperLimit - yLowerLimit
            exponent = int(math.log10(yDelta))
            presicion = -(exponent - 2)
            yStepSize = round(yDelta / yNumTicks, presicion)

            self.setAxisScale(Qwt.QwtPlot.yLeft, yLowerLimit, yUpperLimit, yStepSize)

            self.setAxisScale(Qwt.QwtPlot.xBottom, 0, len(self.timeAxis))
            self.redraw()

        def rescaleAxisX(self, deltaX):
            newLen = len(self.timeAxis) + deltaX
            newLen = max(10, min(newLen, self.dataNumValuesSaved))
            self.timeAxis = arange(newLen)
            self.dataOffsetX = max(0, min(self.dataOffsetX, self.dataNumValuesSaved - len(self.timeAxis)))
            self.rescale()

        def scaleAxisY(self, maxValue):
            self.canvasDisplayHeight = maxValue
            self.rescale()

        def moveCanvas(self, deltaX, deltaY):
            self.dataOffsetX += deltaX * len(self.timeAxis) / float(self.canvas().width())
            self.dataOffsetX = max(0, min(self.dataOffsetX, self.dataNumValuesSaved - len(self.timeAxis)))
            self.canvasOffsetX += deltaX * self.canvasDisplayWidth / self.canvas().width()
            self.canvasOffsetY += deltaY * self.canvasDisplayHeight / self.canvas().height()
            self.rescale()

        def mousePressEvent(self, event):
            self.lastCanvasX = event.x() - self.canvas().x()
            self.lastCanvasY = event.y() - self.canvas().y()
            self.pressedCanvasY = event.y() - self.canvas().y()

        def mouseMoveEvent(self, event):
            canvasX = event.x() - self.canvas().x()
            canvasY = event.y() - self.canvas().y()
            if event.buttons() & Qt.MiddleButton: # middle button moves the canvas
                deltaX = self.lastCanvasX - canvasX
                deltaY = canvasY - self.lastCanvasY
                self.moveCanvas(deltaX, deltaY)
            elif event.buttons() & Qt.RightButton: # right button zooms
                zoomFactor = max(-0.6, min(0.6, (self.lastCanvasY - canvasY) / 20.0 / 2.0))
                deltaY = (self.canvas().height() / 2.0) - self.pressedCanvasY
                self.moveCanvas(0, zoomFactor * deltaY * 1.0225)
                self.scaleAxisY(max(0.005, self.canvasDisplayHeight - (zoomFactor * self.canvasDisplayHeight)))
                self.rescaleAxisX(self.lastCanvasX - canvasX)
            self.lastCanvasX = canvasX
            self.lastCanvasY = canvasY

        def wheelEvent(self, event): # mouse wheel zooms the y-axis
            canvasY = event.y() - self.canvas().y()
            zoomFactor = max(-0.6, min(0.6, (event.delta() / 120) / 6.0))
            deltaY = (self.canvas().height() / 2.0) - canvasY
            self.moveCanvas(0, zoomFactor * deltaY * 1.0225)
            self.scaleAxisY(max(0.0005, self.canvasDisplayHeight - zoomFactor * self.canvasDisplayHeight))


if __name__ == '__main__':
    from PyQt4.QtGui import QApplication

    app = QApplication(sys.argv)
    plot = DataPlot()
    plot.setRedrawInterval(30)
    plot.resize(700, 500)
    plot.show()
    plot.addCurve(0, '(x/500)^2')
    plot.addCurve(1, 'sin(x / 20) * 500')
    for i in range(plot.dataNumValuesSaved):
        plot.updateValue(0, (i / 500.0) * (i / 5.0))
        plot.updateValue(1, math.sin(i / 20.0) * 500)

    sys.exit(app.exec_())
