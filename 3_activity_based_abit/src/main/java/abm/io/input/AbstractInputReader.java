package abm.io.input;


import abm.data.DataSet;

abstract class AbstractInputReader {

    protected final DataSet dataSet;

    AbstractInputReader(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    public abstract void read();
}
