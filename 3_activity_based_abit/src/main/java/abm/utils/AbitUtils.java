package abm.utils;


import org.apache.commons.lang3.SystemUtils;
import org.apache.log4j.Logger;

import java.net.URL;
import java.util.Random;

public class AbitUtils {



    public static final String SEPARATOR = ",";
    private static final int RANDOM_SEED = 1;
    public static final Random randomObject = new Random(RANDOM_SEED);

    public static Random getRandomObject(){
        return randomObject;
    }

    private final static Logger logger = Logger.getLogger(AbitUtils.class);

    public static void loadHdf5Lib() {
        ClassLoader classLoader = AbitUtils.class.getClassLoader();
        logger.info("Trying to set up native hdf5 lib");
        String path = null;
        if(SystemUtils.IS_OS_WINDOWS) {
            logger.info("Detected windows OS.");
            try {
                path = classLoader.getResource("lib/win32/jhdf5.dll").getFile();
                System.load(path);
            } catch(Throwable e) {
                logger.debug("Cannot load 32 bit library. Trying 64 bit next.");
                try {
                    path = classLoader.getResource("lib/win64/jhdf5.dll").getFile();
                    System.load(path);
                }  catch(Throwable e2) {
                    logger.debug("Cannot load 64 bit library.");
                    path = null;
                }
            }
        } else if(SystemUtils.IS_OS_MAC) {
            logger.info("Detected Mac OS.");
            try {
                path = classLoader.getResource("lib/macosx32/libjhdf5.jnilib").getFile();
                System.load(path);
            } catch(Throwable e) {
                logger.debug("Cannot load 32 bit library. Trying 64 bit next.");
                try {
                    path = classLoader.getResource("lib/macosx64/libjhdf5.jnilib").getFile();
                    System.load(path);
                } catch(Throwable e2) {
                    logger.debug("Cannot load 64 bit library.");
                    path = null;
                }
            }
        } else if(SystemUtils.IS_OS_LINUX) {
            logger.info("Detected linux OS.");
            try {
                URL url = classLoader.getResource("lib/linux32/libjhdf5.so");
                if(url == null) {
                    logger.info("Could not find linux 32 lib");
                } else {
                    path = url.getFile();
                    System.load(path);
                }
            } catch(Throwable e) {
                logger.debug("Cannot load 32 bit library. Trying 64 bit next.");
                try {
                    URL url = classLoader.getResource("lib/linux64/libjhdf5.so");
                    if(url == null) {
                        logger.info("Could not find linux 64 lib");
                    } else {
                        path = url.getFile();
                        System.load(path);
                    }
                } catch(Throwable e2) {
                    logger.debug("Cannot load 64 bit library. ");
                    path = null;
                }
            }
        }
        if(path != null) {
            logger.info("Hdf5 library successfully located.");
            System.setProperty("ncsa.hdf.hdf5lib.H5.hdf5lib", path);
        } else {
            logger.warn("Could not load native hdf5 library automatically." +
                    " Any code involving omx matrices will only work if the " +
                    "library was set up in java.library.path");
        }
    }

}
