# python-imager

This Python-based application demonstrates how one might connect an imaging device (i.e. a camera) into the SatOS software platform.
This is not production-ready code, but it is useful for learning how the platform functions.

Currently, imager support is limited to a dummy implementation that picks from a local cache of images at random.
This support will be extended for some physical camera devices in the near future.

## Quickstart

In one terminal, check out the [SatOS Payload SDK](https://github.com/antaris-inc/SatOS-Payload-SDK) and walk through
the instructions up to the point that the payload controller simulator (pc-sim) is running within your build environment (build_env).

In another terminal, build the python-imager docker image in this repository:

```
$ docker build -t python-imager .
```

Next, run a container using the image that was just built:

```
docker run --net=host -v $(pwd)/outbound:/opt/antaris/outbound -it python-imager
```

As images are captured by the payload, they are placed in the local "./outbound" directory.

## Physical Camera Support

This app uses [OpenCV](https://docs.opencv.org/4.x/d1/dfb/intro.html) to interact with physical cameras.

To run the payload app with a real camera, you will need to use some additional environment variables and configure docker to make your device available to the container.
The following is an example of a USB camera connected at /dev/video0 on the host:

```
docker run -e IMAGER_TYPE=opencv -e IMAGER_PARAMS='{"device_index":0}' --device /dev/video0 --net=host -v $(pwd)/outbound:/opt/antaris/outbound -it python-imager
```

If your device is located at a different index (i.e. video3), you must also update the `device_index` parameter.
