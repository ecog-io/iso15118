# ISO15118

Python Implementation of the ISO 15118 -2 [^1] and -20 [^2] protocols

## How to fire it up :fire:

The ISO 15118 -2 and -20 code live in the directory `iso15118`.
The primary dependencies to install the project are the following:

> - Linux
>
>   - MacOS is not fully supported -- see "IPv6 Warning" below
>   - Windows is supported using [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).
>   - Other non-Linux operating systems are not supported
>
> - Poetry [^3]
> - Python >= 3.9

<sub>*If using a Windows machine, follow the same steps as below on a Linux VM.</sub>

There are two recommended ways of running the project:

### Running with Docker

Using Docker has the advantage of starting everything up automatically,
including certificate generation, tests and linting, as well as spawning
both the SECC and EVCC containers.

Building and running the docker file:

```bash
$ make build
$ make dev
```

Note that if Docker is used, the command `make run` will try to get the `.env` file.
The command `make dev` will fetch the contents of `.env.dev.docker` - thus,
in this case, the user does not need to create a `.env` file, as Docker will
automatically fetch the `.env.dev.docker` one.

### Local installation

#### 1. Generate certificates

The project includes a script to help on the generation of -2 and -20 certificates.
This script is located under `iso15118/shared/pki/` directory and is called `create_certs.sh`.
The following command provides a guide for the script usage:

```bash
$ cd iso15118/shared/pki/
$ ./create_certs.sh -h
```

Use the following commands to generate certificates for ISO 15118-2 and 15118-20:

```bash
$ ./create_certs.sh -v iso-2
$ ./create_certs.sh -v iso-20
```

#### 2. Install a current version of the JRE

The JRE engine is only a requirement in Josev Community if using the Java-based
EXI codec (EXIficient)[^4]. Josev Professional uses our own Rust-based EXI codec.

Install the JRE engine with the following command:

```bash
sudo apt update && sudo apt install -y default-jre
```

In Ubuntu, the default version of Java installed by your distribution may not be recent enough.
If so, you can manually install a more recent version of Java and configure it to
be the default:

```bash
sudo apt install openjdk-17-jre
```

Display the different installed versions of Java you have installed:

```bash
update-alternatives --query java
```

Configure the more recent version to be the default:

```bash
update-alternatives --config java
```

Then follow the instructions to configure your desired version.

#### 3. Set up local environment variable configuration

The project includes multiple environmental files, in the root directory, for
different purposes:

- `.env.dev.docker` - ENV file with development settings, tailored to be used with docker
- `.env.dev.local` - ENV file with development settings, tailored to be used with
  the local host

If the user runs the project locally, eg using `$ make build && make run-secc`,
it is required to create a `.env` file, containing the required settings.

To run for local development, simply copy the contents of `.env.dev.local` to `.env`.

**Setting your local network interface**

By default, `.env.dev.local` assumes the presence of an `eth0` network interface.
If you are not using eth0 as your network interface, replace the `NETWORK_INTERFACE` value
in your local `.env` file with the one you are using.

The key-value pairs defined in the `.env` file directly affect the settings
present in `secc_settings.py` and `evcc_settings.py`. In these scripts, the
user will find all the settings that can be configured. For reference,
a table is included below.

#### 4. Install Poetry

We use Poetry to manage dependencies.

The recommended way to install Poetry is to use its installation script.
See https://python-poetry.org/docs/#installation for instructions.

#### 5. Run the SECC/EVCC

For convenience, the Makefile, present in the project, helps you to start up the controllers. Thus, in the terminal run:

```bash
$ make install-local
$ make run-secc
```

The above commands will do the following:

1. Install all dependencies with Poetry
2. Use the Poetry shell to activate the appropriate virtual environment
3. Run the start script for SECC

```bash
$ poetry install
$ poetry run python iso15118/secc/start_secc.py
```

If you wish to run the EVCC instead, use `make run-evcc`. Since the project includes
both the SECC and EVCC side, it is possible to test your application by starting both services.
Similar to the SECC, we can start the EVCC side as follows:

```bash
$ make install-local
$ make run-evcc
```
It is possible to run up EVCC in different configurations. An example setting configuration
for EVCC would be (15118-2, AC, EIM, TLS disabled mode), (15118-2/DINSPEC, DC, EIM/PnC, TLS enabled) etc. 
Examples for such configurations are provided under "iso15118/shared/examples/evcc/". The configuration 
could be passed in as a commandline argument as given below.

```bash
$ make run-evcc config=path_of_config_file
```
Supported settings in EVCC configuration are given below:


| Setting                | Default Value                                                | Description                                                                                                                            |
|----------------------- | ------------------------------------------------------------ |----------------------------------------------------------------------------------------------------------------------------------------|
| supportedProtocols     | `DIN_SPEC_70121,ISO_15118_2,ISO_15118_20_AC,ISO_15118_20_DC` | Enabled communication protocols on EVCC.                                                                                               |
| supportedEnergyServices| `AC`                                                         | Selected energy services mode for EVCC.                                                                                                |
| useTls                 | `True`                                                       | Whether or not the EVCC signals the preference to communicate with a TLS connection                                                    |
| enforceTls             | `False`                                                      | Whether or not the EVCC will only accept TLS connections                                                                               |
| isCertInstallNeeded    | `False`                                                      | Indicates if the installation of a contract certificate is needed                                                                      |
| energyTransferMode     | `AC_three_phase_core`                                        | Energy transfer mode requested for the current charging session.                                                                       |
| sdpRetryCycles         | `1`                                                          | Indicates how often shall SDP (SECC Discovery Protocol) retries happen before reverting to using nominal duty cycle PWM-based charging |
| maxContractCerts       | `3`                                                          | Maximum amount of contract certificates the EV stores.                                                                                 |
| maxSupportingPoints    | `1024`                                                       | Indicates the maximum number of entries the EVCC supports within the sub-elements of a ScheduleTuple                                   |


The SECC and EVCC have been tested together under:

- Linux - Ubuntu and Debian distros
- MacOS

---

## IPv6 WARNING

For the system to work locally, the network interface needs to have
an IPv6 link-local address assigned.

For Docker, the `docker-compose.yml` was configured to create an `IPv6` network
called `ipv6_net`, which enables the containers to acquire a link-local address - this is required to establish an
ISO 15118 communication. This configuration is fine if the user wants to test, in isolation, the EVCC and SECC, and
allow ISO 15118 communication. This configuration works for both Linux and BSD systems.

However, the usage of an internal `ipv6_net` network, in Docker, does not allow the
host to reach link-local addresses. This would pose a problem, as it would require
the application to use the global link address, which is not supported by ISO 15118.

The solution is to use the `network_mode: host` feature of Docker, which replicates
the host network topology within the Docker world, ie the containers and the
host share the same network. This way, Docker can directly access the virtual
network interface created by the HomePlug Green PHY module, making it possible
to use the link-local address.

Currently, `network_mode: host` just works within Linux environments [^5] [^6].
Since the Switch team relies mostly on MacOS and this project is on a development stage,
`network_mode` is not used by default; it is possible to use it, however, if the contents of the
file `docker-compose-host-mode.yml` are copied to the main compose file, `docker-compose.yml`.
In that case, we advise you to back up the compose file.

---

## Environment Settings

The default configuration values can be modified by setting them as environment variables.
The following table provides a few of the available variables:

| ENV                   | Default Value                                                | Description                                                                                                                                                     |
|-----------------------| ------------------------------------------------------------ |-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| NETWORK_INTERFACE     | `eth0`                                                       | HomePlug Green PHY Network Interface from which the high-level communication (HLC) will be established                                                          |
| SECC_ENFORCE_TLS      | `False`                                                      | Whether or not the SECC will enforce a TLS connection                                                                                                           |
| PKI_PATH              | `<CWD>/iso15118/shared/pki/`                                 | Path for the location of the PKI where the certificates are located. By default, the system will look for the PKI directory under the current working directory |
| LOG_LEVEL             | `INFO`                                                       | Level of the Python log service                                                                                                                                 |
| MESSAGE_LOG_JSON      | `True`                                                       | Whether or not to log the EXI JSON messages (only works if log level is set to DEBUG)                                                                           |
| MESSAGE_LOG_EXI       | `False`                                                      | Whether or not to log the EXI Bytestream messages (only works if log level is set to DEBUG)                                                                     |
| PROTOCOLS             | `DIN_SPEC_70121,ISO_15118_2,ISO_15118_20_AC,ISO_15118_20_DC` | Enabled communication protocols on SECC.                                                                                                                        |
| AUTH_MODES            | `EIM,PNC`                                                    | Selected authentication modes for SECC                                                                                                                          |
| USE_CPO_BACKEND       | `False`                                                      | Indicates if backend integration is available to fetch certificates                                                                                             |
| FORCE_TLS_CLIENT_AUTH | `False`                                                      | Forces the TLS Client to send its chain for authentication during SECC-EVCC communication.                                                                      |

## License

Copyright [2022] [Switch]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

[^1]: https://www.iso.org/standard/55366.html
[^2]: https://www.switch-ev.com/blog/new-features-and-timeline-for-iso15118-20
[^3]: https://python-poetry.org/docs/#installation
[^4]: https://exificient.github.io/
[^5]: https://docs.docker.com/network/host/
[^6]: https://docs.docker.com/desktop/mac/networking/
