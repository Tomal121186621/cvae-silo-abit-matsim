package abm.utils;

import abm.data.DataSet;
import abm.properties.AbitResources;

public class PopulationScaler {

    private double scaleFactor = AbitResources.instance.getDouble("population.scale.factor", 1.0);


    public void scaleDownPopulation(DataSet dataSet){

        //scale households

        //remove persons that are not in the selected households

        //remove non occupied jobs keeping a portion of vacant jobs

        //reduce school capacity


    }


}
