package abm.calibration;

import abm.data.DataSet;
import org.json.simple.JSONObject;

import java.io.FileNotFoundException;

public interface ModelComponent {

    void setup() throws FileNotFoundException;

    void load();

    void run() throws FileNotFoundException;

}
