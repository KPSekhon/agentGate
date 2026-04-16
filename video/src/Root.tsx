import { Composition, Still } from "remotion";
import { AgentGateDemo } from "./AgentGateDemo";
import { Thumbnail } from "./Thumbnail";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AgentGateDemo"
        component={AgentGateDemo}
        durationInFrames={2250}
        fps={30}
        width={1920}
        height={1080}
      />
      <Still
        id="Thumbnail"
        component={Thumbnail}
        width={1280}
        height={720}
      />
    </>
  );
};
