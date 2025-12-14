from loguru import logger

import reputils
import reputils.MailReport


def mrsendmail_apply_loguru_patch(skiplog: bool = False) -> None:
    logger.info(f"mrsendmail_apply_loguru_patch({skiplog=})")

    # print("\n", file=sys.stderr, flush=True, end="")
    @classmethod  # type: ignore
    def logtest(cls) -> None:  # type: ignore
        melo = logger.bind(classname=cls.__qualname__)
        with melo.contextualize(skiplog=skiplog):
            # logger = logger.bind(skiplog=skiplog)
            melo.info(f"{__name__=} {skiplog=}")
            melo.debug(f"{__name__=} {skiplog=}")

            # if not skiplog:
            #     print("\n", file=sys.stderr, flush=True, end="")

            # if "__qualname__" in vars():
            melo.info(f"{cls.__qualname__=}")
            melo.debug(f"{cls.__qualname__=}")

            # if not skiplog:
            #     print("\n", file=sys.stderr, flush=True, end="")

    # patch
    reputils.MailReport.MRSendmail.logtest = logtest  # type: ignore[attr-defined]


def main() -> None:
    logger.info(f"in main()::{__name__=} :: before configuring loguru")

    reputils.configure_loguru_default_with_skiplog_filter()

    for t in [False, True]:
        mrsendmail_apply_loguru_patch(skiplog=t)
        logger.info(f"reputils.MailReport.MRSendmail.logtest(skiplog={t}) -> start")
        # print("\n", file=sys.stderr, flush=True, end="")
        reputils.MailReport.MRSendmail.logtest()  # type: ignore[attr-defined]
        # print("\n", file=sys.stderr, flush=True, end="")
        logger.info(f"reputils.MailReport.MRSendmail.logtest(skiplog={t}) -> done")
        # print("\n", file=sys.stderr, flush=True, end="")


if __name__ == "__main__":
    logger.info("INFO-LEVEL (DEBUG-LEVEL FOLLOWS) before main.")
    logger.debug("DEBUG-LEVEL (INFO-LEVEL was before) before main.")
    main()
    logger.info("INFO-LEVEL only after main.")
