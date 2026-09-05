import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Stat,
  Text,
  TextInput,
  useCanvasState,
} from "cursor/canvas";

type Choice = "" | "A" | "B" | "C";

type Option = {
  id: "A" | "B" | "C";
  title: string;
  after: string;
};

type Question = {
  ask: string;
  gap: string;
  recommend: "A" | "B" | "C";
  recommendLabel: "强烈推荐" | "略偏" | "差不多";
  recommendNote: string;
  options: Option[];
};

// 最多三题。把下面三份数据换成这一轮要拍的内容。
const Q1: Question = {
  ask: "（第 1 题一句话）？",
  gap: "A 会……；B 会……。",
  recommend: "A",
  recommendLabel: "略偏",
  recommendNote: "半句原因。",
  options: [
    { id: "A", title: "短名 A", after: "选完会怎样。" },
    { id: "B", title: "短名 B", after: "选完会怎样。" },
  ],
};

const Q2: Question = {
  ask: "（第 2 题一句话）？",
  gap: "A 会……；B 会……。",
  recommend: "A",
  recommendLabel: "强烈推荐",
  recommendNote: "半句原因。",
  options: [
    { id: "A", title: "短名 A", after: "选完会怎样。" },
    { id: "B", title: "短名 B", after: "选完会怎样。" },
  ],
};

const Q3: Question = {
  ask: "（第 3 题一句话）？",
  gap: "A 会……；B 会……。",
  recommend: "A",
  recommendLabel: "差不多",
  recommendNote: "半句原因。",
  options: [
    { id: "A", title: "短名 A", after: "选完会怎样。" },
    { id: "B", title: "短名 B", after: "选完会怎样。" },
  ],
};

function pickOption(question: Question, choice: Choice): Option | undefined {
  if (choice === "A") return question.options[0];
  if (choice === "B") return question.options[1];
  if (choice === "C") return question.options[2];
  return undefined;
}

function OptionRow({
  option,
  recommend,
  onPick,
}: {
  option: Option;
  recommend: "A" | "B" | "C";
  onPick: (id: "A" | "B" | "C") => void;
}) {
  const isRec = option.id === recommend;
  return (
    <Row gap={8} align="center">
      <Button
        variant={isRec ? "primary" : "secondary"}
        onClick={() => onPick(option.id)}
      >
        {option.id} {option.title}
      </Button>
      {isRec ? <Pill size="sm">更推荐</Pill> : null}
      <Text tone="secondary" size="small">
        {option.after}
      </Text>
    </Row>
  );
}

function OpenCard({
  question,
  indexLabel,
  note,
  setNote,
  setChoice,
}: {
  question: Question;
  indexLabel: string;
  note: string;
  setNote: (value: string) => void;
  setChoice: (value: Choice) => void;
}) {
  const a = question.options[0];
  const b = question.options[1];
  const c = question.options[2];
  return (
    <Card>
      <CardHeader trailing={indexLabel}>正在拍</CardHeader>
      <CardBody>
        <Stack gap={12}>
          <Stack gap={4}>
            <Text weight="semibold">{question.ask}</Text>
            <Text tone="secondary" size="small">
              差在哪：{question.gap}
            </Text>
            <Text size="small">
              {question.recommendLabel} {question.recommend}。{question.recommendNote}
            </Text>
          </Stack>
          <Stack gap={8}>
            {a ? (
              <OptionRow
                option={a}
                recommend={question.recommend}
                onPick={setChoice}
              />
            ) : null}
            {b ? (
              <OptionRow
                option={b}
                recommend={question.recommend}
                onPick={setChoice}
              />
            ) : null}
            {c ? (
              <OptionRow
                option={c}
                recommend={question.recommend}
                onPick={setChoice}
              />
            ) : null}
          </Stack>
          <TextInput
            value={note}
            onChange={setNote}
            placeholder="要补一句口径就写这里，可空"
          />
        </Stack>
      </CardBody>
    </Card>
  );
}

function DecidedRow({
  question,
  choice,
  onEdit,
}: {
  question: Question;
  choice: Choice;
  onEdit: () => void;
}) {
  const picked = pickOption(question, choice);
  if (!picked) return null;
  return (
    <Row gap={12} align="center" justify="space-between">
      <Stack gap={4} style={{ flex: 1 }}>
        <Text weight="semibold">{question.ask}</Text>
        <Text tone="secondary" size="small">
          拍了 {picked.id} · {picked.title}
        </Text>
      </Stack>
      <Row gap={8} align="center">
        <Pill size="sm" active>
          {picked.id}
        </Pill>
        <Button variant="ghost" onClick={onEdit}>
          改
        </Button>
      </Row>
    </Row>
  );
}

export default function DecisionBoard() {
  const [q1, setQ1] = useCanvasState<Choice>("pick-q1", "");
  const [q2, setQ2] = useCanvasState<Choice>("pick-q2", "");
  const [q3, setQ3] = useCanvasState<Choice>("pick-q3", "");
  const [n1, setN1] = useCanvasState("note-q1", "");
  const [n2, setN2] = useCanvasState("note-q2", "");
  const [n3, setN3] = useCanvasState("note-q3", "");

  const decidedCount = (q1 ? 1 : 0) + (q2 ? 1 : 0) + (q3 ? 1 : 0);
  const openIndex = decidedCount + 1;

  let open: "q1" | "q2" | "q3" | null = null;
  if (!q1) open = "q1";
  else if (!q2) open = "q2";
  else if (!q3) open = "q3";

  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 720 }}>
      <Stack gap={6}>
        <H1>拍题板</H1>
        <Text tone="secondary">
          一次只摊开一题。选完收成问题和裁决。
        </Text>
      </Stack>

      <Row gap={16}>
        <Stat value={String(3 - decidedCount)} label="还没拍" />
        <Stat
          value={String(decidedCount)}
          label="已拍"
          tone={decidedCount ? "success" : undefined}
        />
      </Row>

      {open === "q1" ? (
        <OpenCard
          question={Q1}
          indexLabel={`${openIndex} / 3`}
          note={n1}
          setNote={setN1}
          setChoice={setQ1}
        />
      ) : null}
      {open === "q2" ? (
        <OpenCard
          question={Q2}
          indexLabel={`${openIndex} / 3`}
          note={n2}
          setNote={setN2}
          setChoice={setQ2}
        />
      ) : null}
      {open === "q3" ? (
        <OpenCard
          question={Q3}
          indexLabel={`${openIndex} / 3`}
          note={n3}
          setNote={setN3}
          setChoice={setQ3}
        />
      ) : null}
      {open === null ? (
        <Callout tone="success" title="三道都拍完了">
          下面只留问题和裁决。要改某一题，点「改」。
        </Callout>
      ) : null}

      {decidedCount > 0 ? (
        <Stack gap={8}>
          <H2>已拍</H2>
          <Stack gap={12}>
            {q1 ? (
              <DecidedRow question={Q1} choice={q1} onEdit={() => setQ1("")} />
            ) : null}
            {q2 ? (
              <DecidedRow question={Q2} choice={q2} onEdit={() => setQ2("")} />
            ) : null}
            {q3 ? (
              <DecidedRow question={Q3} choice={q3} onEdit={() => setQ3("")} />
            ) : null}
          </Stack>
        </Stack>
      ) : null}

      <Divider />
      <Text tone="tertiary" size="small">
        轻量拍题板。这板只记勾选，不当真源。
      </Text>
    </Stack>
  );
}
