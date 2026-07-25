import { PageHeading } from "../../../components/ui";
import { SecurityTestRunner } from "./security-test-runner";

export default function UntrustedContentSecurityTestPage() {
  return (
    <>
      <PageHeading
        eyebrow="Security Tests"
        title="Prompt Injection Regression Test"
        description="验证真实本地代码路径中的不可信内容边界；外部模型行为单独标记为 NOT VERIFIED。"
      />
      <SecurityTestRunner />
    </>
  );
}
