import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { setSessionProjectRoot } from '@aws/agentcore-cdk';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { AgentCoreStack } from '../lib/cdk-stack';

test('AgentCoreStack synthesizes with empty spec', () => {
  // The L3 construct discovers an AgentCore project from the filesystem even
  // when the supplied specification is empty. Build an isolated, disposable
  // project so this test never depends on a developer's local agentcore.json.
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'agentcore-cdk-test-'));
  const configRoot = path.join(projectRoot, 'agentcore');
  fs.mkdirSync(configRoot);
  fs.writeFileSync(path.join(configRoot, 'agentcore.json'), '{}', 'utf8');
  setSessionProjectRoot(projectRoot);

  const app = new cdk.App();
  try {
    const stack = new AgentCoreStack(app, 'TestStack', {
      spec: {
        name: 'testproject',
        version: 1,
        managedBy: 'CDK' as const,
        runtimes: [],
        memories: [],
        credentials: [],
        evaluators: [],
        onlineEvalConfigs: [],
        configBundles: [],
        policyEngines: [],
        payments: [],
        agentCoreGateways: [],
        mcpRuntimeTools: [],
        unassignedTargets: [],
        datasets: [],
        knowledgeBases: [],
      },
    });
    const template = Template.fromStack(stack);
    template.hasOutput('StackNameOutput', {
      Description: 'Name of the CloudFormation Stack',
    });
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
