import { Preview, Section, Text } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperPolar from '../components/WrapperPolar'
import type { schemas } from '../types'

export function PayoutScheduled({
  email,
  formatted_amount,
  account_holder_name,
}: schemas['PayoutScheduledProps']) {
  return (
    <WrapperPolar>
      <Preview>
        A scheduled payout of {formatted_amount} is on its way to your account
      </Preview>
      <Intro>
        {account_holder_name ? (
          <>
            Hi <strong>{account_holder_name}</strong>, a scheduled payout of{' '}
            <strong>{formatted_amount}</strong> is on its way.
          </>
        ) : (
          <>
            A scheduled payout of <strong>{formatted_amount}</strong> is on its
            way to your account.
          </>
        )}
      </Intro>
      <BodyText>
        Based on your payout schedule, we&apos;ve automatically initiated a
        payout of your available balance. Funds are typically deposited to your
        connected bank account within a few business days.
      </BodyText>
      <Section className="mt-6">
        <table className="w-full rounded-lg border border-gray-200">
          <tbody>
            <tr className="border-b border-gray-200 bg-gray-50">
              <td className="p-4">
                <Text className="m-0 text-sm font-semibold text-gray-900">
                  Payout Amount
                </Text>
              </td>
              <td className="p-4 text-right">
                <Text className="m-0 text-sm font-semibold text-gray-900">
                  {formatted_amount}
                </Text>
              </td>
            </tr>
          </tbody>
        </table>
      </Section>
      <BodyText>
        You can review this payout, download its invoice, and manage your payout
        schedule from your finance settings on Polar.
      </BodyText>
      <Footer email={email} />
    </WrapperPolar>
  )
}

PayoutScheduled.PreviewProps = {
  email: 'admin@example.com',
  formatted_amount: '$50.00',
  account_holder_name: 'Acme Inc.',
}

export default PayoutScheduled
