import powerfactory as pf
import devices as dev

import logging.config
from logging_config import configure_logging as cl


def main(app):

    # Energex device
    # prot_dev = dev.ProtectionDevice(
    #     app,
    #     row["patternname"],
    #     row["nameenu"],
    #     row["relaysettingid"],
    #     row["datesetting"],
    #     device,
    #     device_id,
    # )

    # Ergon device



if __name__ == "__main__":

    app = pf.GetApplication()
    # Configure logging
    logging.basicConfig(
        filename=cl.getpath() / 'ips_to_pf_log.txt',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    updates = main(app)