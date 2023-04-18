# python-imager

This Python-based application demonstrates how one might connect an imaging device (i.e. a camera) into the SatOS software platform.
This is not production-ready code, but it is useful for learning how the platform functions.

Currently, imager support is limited to a dummy implementation that picks from a local cache of images at random.
This support will be extended for some physical camera devices in the near future.

## Quickstart

In the Antaris Cloud Platform, create a TrueTwin Satellite with a remote payload and download the associated config.
Place that downloaded zip file in this directory.

Build the python-imager app using the following command:

```
docker build --platform=linux/amd64 -t python-imager .
```

Next, we can run the application in a container. The command below assumes that `CONFIG` is set to the name of the downloaded file in your current working directory. The `outbound` directory will also be created and mounted from your local workspace into the container:

```
docker run --platform=linux/amd64 -e CONFIG=$CONFIG -v $(pwd)/$CONFIG:/workspace -v $(pwd)/outbound:/opt/antaris/outbound -it python-imager
```

You may now use the Antaris Cloud Platform to submit payload sequences. For example, submitting a `CaptureAdhoc` payload
sequence will cause an image to be taken, then dropped into the `./outbound` directory for review.

## Physical Camera Support

This app uses [OpenCV](https://docs.opencv.org/4.x/d1/dfb/intro.html) to interact with physical cameras.

To run the payload app with a real camera, you will need to use some additional environment variables and configure docker to make your device available to the container.
The following is an example of a USB camera connected at /dev/video0 on the host:

```
docker run -e IMAGER_TYPE=opencv -e IMAGER_PARAMS='{"device_index":0}' --device /dev/video0 --net=host -v $(pwd)/outbound:/opt/antaris/outbound -it python-imager
```

If your device is located at a different index (i.e. video3), you must also update the `device_index` parameter.
