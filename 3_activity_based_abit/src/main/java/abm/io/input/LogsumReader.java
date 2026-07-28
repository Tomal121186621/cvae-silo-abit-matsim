package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.Zone;
import abm.data.plans.Purpose;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.Id;
import de.tum.bgu.msm.util.MitoUtil;
import de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.GZIPInputStream;

public class LogsumReader implements Reader{
    private static final Logger logger = Logger.getLogger(LogsumReader.class);
    private int positionOrigin;
    private int positionDestination;
    private int positionValue;
    private BufferedReader reader;
    private int numberOfRecords = 0;
    String delimiter = ",";
    double factor = 1.0;
    private DataSet dataSet;

    private Map<String, Map<Purpose, String>> logsumPaths;
    private final String[] roles = {"evOwner", "nonEvOwner"};
    private Map<Integer, Zone> zoneMap;
    private final Map<String, Map<Purpose, IndexedDoubleMatrix2D>> logsumMatrixes;

    public LogsumReader(DataSet dataSet) {
        this.dataSet = dataSet;

        this.logsumPaths = new HashMap<>();

        this.logsumPaths.putIfAbsent("evOwner", new HashMap<>());
        this.logsumPaths.putIfAbsent("nonEvOwner", new HashMap<>());

        if (Boolean.parseBoolean(AbitResources.instance.getString("scenario.lowEmissionZone"))){
            this.logsumPaths.get("evOwner").put(Purpose.SHOPPING, AbitResources.instance.getString("logsum.evOwner.SHOPPING.base"));
            this.logsumPaths.get("evOwner").put(Purpose.ACCOMPANY, AbitResources.instance.getString("logsum.evOwner.ACCOMPANY.base"));
            this.logsumPaths.get("evOwner").put(Purpose.OTHER, AbitResources.instance.getString("logsum.evOwner.OTHER.base"));
            this.logsumPaths.get("evOwner").put(Purpose.RECREATION, AbitResources.instance.getString("logsum.evOwner.RECREATION.base"));
            this.logsumPaths.get("evOwner").put(Purpose.WORK, AbitResources.instance.getString("logsum.evOwner.WORK.base"));
            this.logsumPaths.get("evOwner").put(Purpose.EDUCATION, AbitResources.instance.getString("logsum.evOwner.EDUCATION.base"));

            this.logsumPaths.get("nonEvOwner").put(Purpose.SHOPPING, AbitResources.instance.getString("logsum.nonEvOwner.SHOPPING.lez"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.ACCOMPANY, AbitResources.instance.getString("logsum.nonEvOwner.ACCOMPANY.lez"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.OTHER, AbitResources.instance.getString("logsum.nonEvOwner.OTHER.lez"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.RECREATION, AbitResources.instance.getString("logsum.nonEvOwner.RECREATION.lez"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.WORK, AbitResources.instance.getString("logsum.nonEvOwner.WORK.lez"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.EDUCATION, AbitResources.instance.getString("logsum.nonEvOwner.EDUCATION.lez"));
        }else{
            this.logsumPaths.get("evOwner").put(Purpose.SHOPPING, AbitResources.instance.getString("logsum.evOwner.SHOPPING.base"));
            this.logsumPaths.get("evOwner").put(Purpose.ACCOMPANY, AbitResources.instance.getString("logsum.evOwner.ACCOMPANY.base"));
            this.logsumPaths.get("evOwner").put(Purpose.OTHER, AbitResources.instance.getString("logsum.evOwner.OTHER.base"));
            this.logsumPaths.get("evOwner").put(Purpose.RECREATION, AbitResources.instance.getString("logsum.evOwner.RECREATION.base"));
            this.logsumPaths.get("evOwner").put(Purpose.WORK, AbitResources.instance.getString("logsum.evOwner.WORK.base"));
            this.logsumPaths.get("evOwner").put(Purpose.EDUCATION, AbitResources.instance.getString("logsum.evOwner.EDUCATION.base"));

            this.logsumPaths.get("nonEvOwner").put(Purpose.SHOPPING, AbitResources.instance.getString("logsum.nonEvOwner.SHOPPING.base"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.ACCOMPANY, AbitResources.instance.getString("logsum.nonEvOwner.ACCOMPANY.base"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.OTHER, AbitResources.instance.getString("logsum.nonEvOwner.OTHER.base"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.RECREATION, AbitResources.instance.getString("logsum.nonEvOwner.RECREATION.base"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.WORK, AbitResources.instance.getString("logsum.nonEvOwner.WORK.base"));
            this.logsumPaths.get("nonEvOwner").put(Purpose.EDUCATION, AbitResources.instance.getString("logsum.nonEvOwner.EDUCATION.base"));
        }



        this.logsumMatrixes = this.dataSet.getLogsums();
        this.logsumMatrixes.putIfAbsent("evOwner", new HashMap<>());
        this.logsumMatrixes.putIfAbsent("nonEvOwner", new HashMap<>());

        this.zoneMap = this.dataSet.getZones();
    }

    @Override
    public void read() {
        for (String role : this.roles) {
            for (Purpose purpose : Purpose.getAllPurposes()) {
                String path = this.logsumPaths.get(role).get(purpose);
                IndexedDoubleMatrix2D logsumMatrix = this.readAndConvertToDoubleMatrix2D(path, this.factor, this.zoneMap.values());
                this.logsumMatrixes.get(role).put(purpose, logsumMatrix);
            }
        }
    }

    private IndexedDoubleMatrix2D readAndConvertToDoubleMatrix2D(String fileName, double factor, Collection<? extends Id> zoneLookup) {
        this.initializeReader(fileName, delimiter);

        IndexedDoubleMatrix2D matrix = new IndexedDoubleMatrix2D(zoneLookup, zoneLookup);
        matrix.assign(Double.MAX_VALUE);

        this.readMatrix(matrix);
        return matrix;
    }
    private void initializeReader(String filePath, String delimiter) {
        try {
            GZIPInputStream in = new GZIPInputStream(new FileInputStream(filePath));
            reader = new BufferedReader(new InputStreamReader(in));
            processHeader(reader.readLine().split(delimiter));
        } catch (IOException e) {
            logger.error("Error initializing csv.gz reader: " + e.getMessage(), e);
        }
    }

    private void readMatrix(IndexedDoubleMatrix2D matrix) {
        try {
            String record;
            while ((record = reader.readLine()) != null) {
                numberOfRecords++;
                if (numberOfRecords % 1000000 == 0){
                    logger.info("Read " + numberOfRecords + " records.");
                }

                processRecord(record.split(delimiter), matrix);
            }
        } catch (IOException e) {
            logger.error("Error parsing record number " + numberOfRecords + ": " + e.getMessage(), e);
        } finally {
            try {
                reader.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        logger.info(this.getClass().getSimpleName() + ": Read " + numberOfRecords + " records.");
    }
    private void processHeader(String[] header) {
        positionOrigin = MitoUtil.findPositionInArray("origin", header);
        positionDestination = MitoUtil.findPositionInArray("destination", header);
        positionValue = MitoUtil.findPositionInArray("logsum", header);
    }

    private void processRecord(String[] record, IndexedDoubleMatrix2D matrix) {
        int origin = Integer.parseInt(record[positionOrigin]);
        int destination = Integer.parseInt(record[positionDestination]);
        double logsum = Double.parseDouble(record[positionValue]) * this.factor;
        if (!Double.isNaN(logsum)){
            matrix.setIndexed(origin, destination, logsum);
        } else {
            logger.warn("Logsum is NaN for origin " + origin + " and destination " + destination);
        }
    }
}
