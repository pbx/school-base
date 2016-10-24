from barcode import *

class Code39(BarCode):
    
    wide = 0        # width of wide bar or space
    narrow = 0      # width of narrow bar or space
    encoded = 0      # encode string 1 & 0's 
    elements = 0    # array of various bars: wide black, narrow black, wide white, narrow white
    message = ''    # the actual barcode message
    '''
    The constructor of the barcode
    '''
    def __init__(self):
        super(Code39,self).__init__(height=1,width=0,factor=0)
        
        self.setFactor(1)
        self.createSymbolSet()
        self.createElements()
        
    def setValue(self,value): 
        self.value = value
        self.message = ('*' + value + '*').upper()
    
    def setFactor(self,factor):
        self.factor = factor
        self.height = factor * 30
        self.wide = factor * 5
        self.narrow = factor * 2
        
    def generateStyles(self):
        '''
        Create the CSS styles to deal with the bar code
        '''
        self.style = """
            <style>
            .barcode {
                border:5px solid #fff;
                background:#fff;
                width:%dpx;
                text-align:center;
                %s
            }
            .ns {
                border-left:%dpx solid #fff;
                height:%dpx;
            }
            .nb {
                border-left:%dpx solid #000;
                height:%dpx;
            }    
            .ws {
                border-left:%dpx solid #fff;
                height:%dpx;
            }
            .wb {
                border-left:%dpx solid #000;
                height:%dpx;
            }
            </style>
            """ % (self.width,self.divStyle,self.narrow,self.height,self.narrow,self.height,self.wide,self.height,self.wide,self.height)
    
    def generateHTML(self):
        self.encode();
        self.html += "<div class='barcode' id='%s_bc'>%s<br />%s</div>\n" % (self.name,self.encoded,self.value)
        
    def createSymbolSet(self):
        # 0 = narrow
        # 1 = wide
        # added inner-charater narrow bar
        self.symbolSet      = {}
        self.symbolSet['0'] = '0001101000'
        self.symbolSet['1'] = '1001000010'
        self.symbolSet['2'] = '0011000010'
        self.symbolSet['3'] = '1011000000'
        self.symbolSet['4'] = '0001100010'
        self.symbolSet['5'] = '1001100000'
        self.symbolSet['6'] = '0011100000'
        self.symbolSet['7'] = '0001001010'
        self.symbolSet['8'] = '1001001000'
        self.symbolSet['9'] = '0011001000'
        self.symbolSet['A'] = '0011001000'
        self.symbolSet['B'] = '0010010010'
        self.symbolSet['C'] = '1010010000'
        self.symbolSet['D'] = '0000110010'
        self.symbolSet['E'] = '1000110000'
        self.symbolSet['F'] = '0010110000'
        self.symbolSet['G'] = '0000011010'
        self.symbolSet['H'] = '1000011000'
        self.symbolSet['I'] = '0010011000'
        self.symbolSet['J'] = '0000111000'
        self.symbolSet['K'] = '1000000110'
        self.symbolSet['L'] = '0010000110'
        self.symbolSet['M'] = '1010000100'
        self.symbolSet['N'] = '0000100110'
        self.symbolSet['O'] = '1000100100'
        self.symbolSet['P'] = '0010100100'
        self.symbolSet['Q'] = '0000001110'
        self.symbolSet['R'] = '1000001100'
        self.symbolSet['S'] = '0010001100'
        self.symbolSet['T'] = '0000101100'
        self.symbolSet['U'] = '1100000010'
        self.symbolSet['V'] = '0110000010'
        self.symbolSet['W'] = '1110000000'
        self.symbolSet['X'] = '0100100010'
        self.symbolSet['Y'] = '1100100000'
        self.symbolSet['Z'] = '0110100000'
        self.symbolSet['-'] = '0100001010'
        self.symbolSet['.'] = '1100001000'
        self.symbolSet[' '] = '0110001000'
        self.symbolSet['`'] = '0110001000'
        self.symbolSet['$'] = '0101010000'
        self.symbolSet['/'] = '0101000100'
        self.symbolSet['+'] = '0100010100'
        self.symbolSet['%'] = '0001010100'
        self.symbolSet['*'] = '0100101000'
        
    def createElements(self):
        self.elements = [["<span class='ns'></span>","<span class='nb'></span>"],["<span class='ws'></span>","<span class='wb'></span>"]]
        # self.elements[0][0] = "<span class='ns'></span>" narrow space
        # self.elements[0][1] = "<span class='nb'></span>" narrow bar
        # self.elements[1][0] = "<span class='ws'></span>" wide space
        # self.elements[1][1] = "<span class='wb'></span>" wide bar
        
    def getWidth(self):
        ans = (self.narrow * 7 * len(self.message)) + (self.wide * 3 * len(self.message)) + len(self.message) + 10
        return ans
    
    def encode(self):
        self.encoded = '';
        # Code 3 of 9
        color = 1 # black = 1, white = 0
        for i in range(len(self.message)):
            code = self.symbolSet[self.message[i]]
            for j in range(10):
                width = int(code[j])
                self.encoded += self.elements[width][color]
                if (color == 1):
                    color = 0
                else:
                    color = 1
                
