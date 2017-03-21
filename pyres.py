from __future__ import division
import pandas as pd
from functools import partial

class ReservoirModel(object):
    """A reservoir model frameworks
    """

    def __init__(self, config_path = None):
        if config_path is None:
            self.period = None
            self._createEmptyDatabase()
            self.iterator = 0

    def __str__(self):
        """This is the string that is printed"""
        # TODO Modify str method to be more representative
        return self.__class__.__name__

    def __repr__(self):
        """This string recreate the object"""
        return "{}()".format(self.__class__.__name__)

    @property
    def reservoirs(self):
        return self._resDf

    @property
    def parameters(self):
        return self._paramDf

    @property
    def variables(self):
        return self._varDf

    @property
    def connections(self):
        return self._conDf

    @property
    def inputs(self):
        return self._inDf
    
    @property
    def monitors(self):
        return self._monDf
    
    @property
    def outputs(self):
        return self._outDf

    def setPeriod(self, pd_period=None):
        """Set period for the modelling
        pd_period = pd.date_range
        """

    def addReservoir(self, name=None, run_order=None):
        """Add a reservoir to the model.
        
        `addReservoir` creates a `pyres.Reservoir(name=name,
        model = self)` object. As the model is passed into the
        reservoir, it is possible to retrieve the model from
        the reservoir by using `Reservoir.model`.
        
        The reservoirs are stored into a `pandas.DataFrame`.
        
        A reservoir is retrieved using `getReservoir` method.
        
        
        Parameters
        ----------
        name : str
            Name of the reservoir
        run_order : int
            Set comparative position to call `Reservoir._updateState`        
        """
        
        row_ix = len(self._resDf)
        self._resDf.loc[row_ix] = (name, run_order, Reservoir(name=name,model=self))

    def addInputData(self, name=None, path=None, **kwargs):
        """Add an input to the model
        """
        inputData = InputData(name, path, **kwargs)
        if self.period is None:
            self.period = inputData.data['Time']
        self._inDf.loc[len(self._inDf)] = (name, inputData, path)
        

    def addParameter(self, name=None, value=None, target=None):
        """Add a parameter to a reservoir
        """
        if target == 'global':
            obj = self
        else:
            obj = self.getReservoir(target)
            
        if callable(value):
           self._bindMethod(obj, name, value)
        else:
            setattr(obj, name, value)

        self._paramDf.loc[len(self._paramDf)] = (name, value, target)

    def addVariable(self, name=None, init_value=None, target=None, monitor=False):
        """Add a variable to a reservoir
        """
        if monitor:
            self.addMonitor(target,name)
            arr = pd.np.zeros(len(self.period))
            arr[0] = init_value
            self._addOutputVar(name, arr)
            init_value = arr
            
        res = self.getReservoir(target)
        setattr(res, name, init_value)
        self._varDf.loc[len(self._varDf)] = (name, init_value, target)
        
    def addDynamic(self, target_name, func):
        """Add stepwise dynamical equation to a reservoir
        """
        res = self.getReservoir(target_name)
        self._bindMethod(res, 'updateState', func)
        
    def addMonitor(self, res_name, var_name):
        self._monDf.loc[len(self._monDf)] = (var_name, res_name)


    def connectInput(self, input_name, target_name):
        """Connect an input to a reservoir.
        """
        source_type = 'InputData'
        res = self.getReservoir(target_name)
        in_data = self.getInputData(input_name)
        setattr(res, input_name, in_data)
        self._conDf.loc[len(self._conDf)] = (
            source_type, input_name, target_name, input_name)

    def connectReservoirs(self, source_name, target_name, binders):
        """Connect two reservoirs.
        by adding to the target reservoir a method 
        to retrieve a variable from the source reservoir
        binders type dict
        """
        source_type = 'Reservoir'
        s_res = self.getReservoir(source_name)
        t_res = self.getReservoir(target_name)
        for key, value in binders.iteritems():
            def getVar(self):
                return getattr(s_res, key)
            setattr(t_res, value, partial(getVar, t_res))

        self._conDf.loc[len(self._conDf)] = (
            source_type, source_name, target_name, binders)

    def getReservoir(self, res_name):
        """Get a reservoir by name
        """
        row = self._resDf[self._resDf['name'] == res_name]
        res = row.iloc[0]['object']
        return res

    def getInputData(self, input_name):
        """Get an Input by name
        """
        row = self._inDf[self._inDf['name'] == input_name]
        data = row.iloc[0]['object'].data
        return data
    
    def getReservoirByVarName(self, var_name):
        variables = self._varDf.set_index('name')
        res_name = variables.loc[var_name]['target']
        return self.getReservoir(res_name)
        
    
    def run(self, stop=None):
        if not stop:
            stop = len(self.period)
        self.iterator = 0
        seq  = range(stop)
        for i in seq:
            print "\r{0}".format((float(i)/stop)*100),
            for j in self._resDf.sort_values('order').iterrows():
                res = self.getReservoir(j[1]['name'])
                res.updateState()
            self._recOutputs()
            self.iterator += 1
    
    def saveConfig(self, path=None):
        import json
        with open(path, 'w') as outfile:
            config = {
                'reservoirs': self.reservoirs.to_dict(),
                'parameters': self.parameters.to_dict(),
                'variables': self.variables.to_dict(),
                'inputs': self.inputs.to_dict(),
                'connections': self.connections.to_dict()            
            }
            print config
            json.dump(config, outfile)
        

    # Graphviz
    def flowChart(self):
        import pydot as pdt
        from matplotlib import pyplot as plt
        import matplotlib.image as mpimg
        graph = pdt.Dot(graph_type='digraph')
        nodes = {}
        for i, res in self._resDf.iterrows():
            node = pdt.Node(res['name'])
            nodes[res['name']] = node
            graph.add_node(node)
        for i, inp in self._inDf.iterrows():
            node = pdt.Node(inp['name'])
            nodes[inp['name']] = node
        for i, con in self._conDf.iterrows():
            edge = pdt.Edge(nodes[con['source']], nodes[con['target']])
            graph.add_edge(edge)
        graph.write_png('model.png')
        m_map = mpimg.imread('model.png')
        plt.imshow(m_map)
        plt.axis('off')

    # Private functions
    
    def _bindMethod(self, obj, method_name, func):
        """Bind a function and store it in an object"""
        setattr(obj, method_name, partial(func,obj))

    def _addOutputVar(self, var_name, arr):
        """Add an output to the output table
        """
        if self._outDf.empty:
            self._outDf[self.period.name] = self.period
            self._outDf.set_index(self.period.name, inplace=True)
        self._outDf[var_name] = arr
            
    def _recOutputs(self):
        cols = self._outDf.columns
        vals = [self._getOutputVar(i) for i in cols]
        self._outDf.iloc[self.iterator]=vals
        
    def _getOutputVar(self, var_name):
        res = self.getReservoirByVarName(var_name)
        return getattr(res, var_name)[self.iterator]
    
    def _createEmptyDatabase(self):
        self._resDf = pd.DataFrame(columns=['name','order', 'object'])
        self._inDf = pd.DataFrame(columns=['name','object', 'path'])
        self._conDf = pd.DataFrame(
            columns=['souceType', 'source', 'target', 'var'])
        self._paramDf = pd.DataFrame(columns=['name', 'value', 'target'])
        self._varDf = pd.DataFrame(columns=['name', 'init_value', 'target'])
        self._monDf = pd.DataFrame(columns=['name', 'target'])
        self._outDf = pd.DataFrame()

    # wrappers

    def _checkInputLenght(self, ts):
        return self.period == len(ts)

    def _checkInputName(self):
        pass

    def _checkVariableName(self):
        pass


class Reservoir(object):

    def __init__(self, name, model):
        self.name = name
        self.model = model

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return "{}(name={}, model={})".format(self.__class__.__name__, self.name, self.model)
        
    @property
    def time(self):
        return self.model.iterator
        
    def _updateState(self):
        """A user defined method 
        
        ``_updateState`` update the variables of the reservoir
        """
        pass

class InputData(object):

    def __init__(self, name, path, **kwargs):
        self.data = pd.read_csv(path, **kwargs)
        col1 = self.data.columns[0]
        col2 = self.data.columns[1]
        self.data.rename(columns={col1: 'Time', col2: name}, inplace=True)

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return "{}()".format(self.__class__.__name__)
