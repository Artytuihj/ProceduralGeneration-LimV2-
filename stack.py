class Stack:
    def __init__(self):
        self.actual_list = []

    def pushEnd(self,item):
        self.actual_list.append(item)

    def peakEnd(self):
        return self.actual_list[-1]

    def pullEnd(self):
        return self.actual_list.pop()

    def getLen(self):
        return len(self.actual_list)