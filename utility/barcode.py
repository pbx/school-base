'''
Produces barcodes.  Kinda obvious.
'''
class BarCode(object):
    name = ''
    value = ''
    
    factor = 0 # size Factor
    width = 0 # height of bars
    height = 1 # width of barcode plus borders
    divStyle = '' # outer div style
    
    #output
    html = ''
    style = ''
    def __init__(self,height=1,width=0,factor=0):
        self.factor = factor
        self.width = width
        self.height = height
    
    def setValue(self,value):
        self.value = value
        
    def setFactor(self,factor):
        self.factor = factor    
    
    def setName(self,name):
        self.name = name
    
    def getStyle(self):
        return self.style
    
    def getHTML(self):
        return self.html
        
    def getBarcode(self):
        return self.style + self.html
        
