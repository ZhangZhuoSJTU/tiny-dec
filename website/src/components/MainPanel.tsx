import STAGES from "../data/stages";
import HeroView from "./HeroView";
import CompletionView from "./CompletionView";
import TextPanel from "./TextPanel";
import CFGPanel from "./CFGPanel";

interface Props {
  current: number;
}

const TOTAL = 1 + STAGES.length + 1;

export default function MainPanel({ current }: Props) {
  if (current === 0) return <HeroView />;
  if (current === TOTAL - 1) return <CompletionView />;

  const stageIdx = current - 1;
  const stage = STAGES[stageIdx];
  const prevStage = stageIdx > 0 ? STAGES[stageIdx - 1] : undefined;

  if (!stage) return null;

  if (stage.viewMode === "cfg" && stage.cfg) {
    return <CFGPanel stage={stage} prevStage={prevStage?.viewMode === "cfg" ? prevStage : undefined} />;
  }

  return <TextPanel stage={stage} prevStage={prevStage} />;
}
