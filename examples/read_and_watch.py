from nano_ctl_connect import MotionClient


def main() -> None:
    # Hardware is initialized by the backend before it accepts RPCs.
    with MotionClient("127.0.0.1:50051") as client:
        result = client.read_axes(0, [0, 1])
        for axis in result.axes:
            print(axis.ref.axis, axis.encoder_position, axis.current_speed)

        # Streams keep one gRPC connection open. Stop by closing the client,
        # cancelling the iterator, or handling KeyboardInterrupt in the app.
        for batch in client.watch_axes(0, [0, 1], interval_micros=10_000):
            print(batch.sampled_at_unix_nano, [item.done for item in batch.axes])


if __name__ == "__main__":
    main()
