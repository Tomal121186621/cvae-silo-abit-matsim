package abm.calibration;

import abm.data.plans.Mode;

import java.io.FileNotFoundException;
import java.util.Map;

public class DayOfWeekMandatoryAssignmentCalibration implements ModelComponent{
    //Todo define a few calibration parameters
    @Override
    public void setup() {
        //Todo: read boolean input from the property file and create the model which needs to be calibrated

        //Todo: initialize all the data containers that might be needed for calibration
    }

    @Override
    public void load() {
        //Todo: read objective values

        //Todo: consider having the result summarization in the statistics writer
    }

    @Override
    public void run() {

        //Todo: loop through the calibration process until criteria are met



        //Todo: obtain the updated coefficients + calibration factors


        //Todo: print the coefficients table to input folder

    }

    private void readObjectiveValues() {

    }

    private void summarizeSimulatedResult() {

    }

    private void printFinalCoefficientsTable(Map<Mode, Map<String, Double>> finalCoefficientsTable) throws FileNotFoundException {

    }
}
