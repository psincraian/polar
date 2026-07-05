import { toast } from '@/components/Toast/use-toast'
import { useUpdateAccount } from '@/hooks/queries'
import { setValidationErrors } from '@/utils/api/errors'
import { isValidationError, schemas } from '@polar-sh/client'
import Button from '@polar-sh/ui/components/atoms/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@polar-sh/ui/components/atoms/Select'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@polar-sh/ui/components/ui/form'
import { useCallback } from 'react'
import { useForm } from 'react-hook-form'

type PayoutScheduleFormValues = {
  payout_schedule: schemas['PayoutSchedule']
  payout_schedule_weekday: string
  payout_schedule_day_of_month: string
}

const WEEKDAYS: { value: string; label: string }[] = [
  { value: '0', label: 'Monday' },
  { value: '1', label: 'Tuesday' },
  { value: '2', label: 'Wednesday' },
  { value: '3', label: 'Thursday' },
  { value: '4', label: 'Friday' },
  { value: '5', label: 'Saturday' },
  { value: '6', label: 'Sunday' },
]

const LAST_DAY_OF_MONTH = '31'

const ordinal = (day: number): string => {
  const suffixes: Record<number, string> = { 1: 'st', 2: 'nd', 3: 'rd' }
  const remainder = day % 100
  if (remainder >= 11 && remainder <= 13) {
    return `${day}th`
  }
  return `${day}${suffixes[day % 10] ?? 'th'}`
}

// Days 1-28 always exist in every month; "Last day of the month" (31) covers
// the last-day case and clamps to shorter months on the backend.
const DAYS_OF_MONTH: { value: string; label: string }[] = [
  ...Array.from({ length: 28 }, (_, index) => {
    const day = index + 1
    return { value: `${day}`, label: `${ordinal(day)} of the month` }
  }),
  { value: LAST_DAY_OF_MONTH, label: 'Last day of the month' },
]

const PayoutScheduleForm = ({ account }: { account: schemas['Account'] }) => {
  const updateAccount = useUpdateAccount()

  const form = useForm<PayoutScheduleFormValues>({
    defaultValues: {
      payout_schedule: account.payout_schedule ?? 'manual',
      payout_schedule_weekday:
        account.payout_schedule_weekday != null
          ? `${account.payout_schedule_weekday}`
          : '0',
      payout_schedule_day_of_month:
        account.payout_schedule_day_of_month != null
          ? `${account.payout_schedule_day_of_month}`
          : '1',
    },
  })

  const {
    control,
    handleSubmit,
    watch,
    setError,
    reset,
    formState: { isDirty },
  } = form

  const schedule = watch('payout_schedule')

  const onSubmit = useCallback(
    async (values: PayoutScheduleFormValues) => {
      const body: schemas['AccountUpdate'] = {
        payout_schedule: values.payout_schedule,
        payout_schedule_weekday:
          values.payout_schedule === 'weekly'
            ? Number(values.payout_schedule_weekday)
            : null,
        payout_schedule_day_of_month:
          values.payout_schedule === 'monthly'
            ? Number(values.payout_schedule_day_of_month)
            : null,
      }

      const { data, error } = await updateAccount.mutateAsync({
        id: account.id,
        body,
      })

      if (error) {
        if (isValidationError(error.detail)) {
          setValidationErrors(error.detail, setError)
        } else {
          toast({
            title: 'Could not update payout schedule',
            description: 'Please try again later.',
          })
        }
        return
      }

      reset({
        payout_schedule: data.payout_schedule ?? 'manual',
        payout_schedule_weekday:
          data.payout_schedule_weekday != null
            ? `${data.payout_schedule_weekday}`
            : '0',
        payout_schedule_day_of_month:
          data.payout_schedule_day_of_month != null
            ? `${data.payout_schedule_day_of_month}`
            : '1',
      })

      toast({
        title: 'Payout schedule updated',
        description:
          data.payout_schedule === 'manual'
            ? 'Payouts will only be created manually.'
            : 'Your payouts will now be created automatically.',
      })
    },
    [account.id, updateAccount, setError, reset],
  )

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-y-6">
        <FormField
          control={control}
          name="payout_schedule"
          render={({ field }) => (
            <FormItem className="flex flex-col gap-1">
              <FormLabel>Schedule</FormLabel>
              <FormControl>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a schedule" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormDescription>
                Automatically create a payout of your available balance on a
                recurring schedule. You&apos;ll receive an email each time a
                scheduled payout is initiated.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {schedule === 'weekly' && (
          <FormField
            control={control}
            name="payout_schedule_weekday"
            render={({ field }) => (
              <FormItem className="flex flex-col gap-1">
                <FormLabel>Day of the week</FormLabel>
                <FormControl>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a day" />
                    </SelectTrigger>
                    <SelectContent>
                      {WEEKDAYS.map((weekday) => (
                        <SelectItem key={weekday.value} value={weekday.value}>
                          {weekday.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {schedule === 'monthly' && (
          <FormField
            control={control}
            name="payout_schedule_day_of_month"
            render={({ field }) => (
              <FormItem className="flex flex-col gap-1">
                <FormLabel>Day of the month</FormLabel>
                <FormControl>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a day" />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS_OF_MONTH.map((day) => (
                        <SelectItem key={day.value} value={day.value}>
                          {day.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <Button
          type="submit"
          className="self-start"
          loading={updateAccount.isPending}
          disabled={updateAccount.isPending || !isDirty}
        >
          Save schedule
        </Button>
      </form>
    </Form>
  )
}

export default PayoutScheduleForm
